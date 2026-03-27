import re
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.ingestion.freesound_client import FreesoundClient
from app.ingestion.freesound_ingestor import (
    extract_author,
    extract_preview_url,
    normalize_freesound_source_page_url,
)
from app.models import Sound, SoundFeatures
from app.schemas import PaginatedResponse, SoundDetail, SoundFeatures as SoundFeaturesSchema, SoundSummary
from app.services.search import build_sound_search_query


router = APIRouter(prefix="/api/sounds", tags=["sounds"])

FREESOUND_OWNER_RE = re.compile(r"/people/(?P<owner>[^/]+)/sounds/")
FREESOUND_PREVIEW_RE = re.compile(
    r"^https://cdn\.freesound\.org/previews/(?P<bucket>\d+)/(?P<sound_id>\d+)_(?P<token>\d+)-(?P<quality>hq|lq)\.mp3$"
)
FREESOUND_DOWNLOAD_RE = re.compile(r"^https://freesound\.org/apiv2/sounds/\d+/download/?$")


def _extract_freesound_owner(source_page_url: Optional[str]) -> Optional[str]:
    if not source_page_url:
        return None

    match = FREESOUND_OWNER_RE.search(source_page_url)
    if not match:
        return None

    return match.group("owner")


def _infer_freesound_preview_url(sound: Sound, db: Session) -> Optional[str]:
    if sound.source != "freesound" or sound.preview_url or not sound.source_sound_id:
        return sound.preview_url

    preview_seed_url: Optional[str] = None

    if sound.author:
        preview_seed_url = db.execute(
            select(Sound.preview_url)
            .where(
                Sound.source == "freesound",
                Sound.author == sound.author,
                Sound.preview_url.is_not(None),
            )
            .limit(1)
        ).scalar_one_or_none()

    if not preview_seed_url:
        owner = _extract_freesound_owner(sound.source_page_url)
        if owner:
            preview_seed_url = db.execute(
                select(Sound.preview_url)
                .where(
                    Sound.source == "freesound",
                    Sound.source_page_url.like(f"%/people/{owner}/sounds/%"),
                    Sound.preview_url.is_not(None),
                )
                .limit(1)
            ).scalar_one_or_none()
            if owner and not sound.author:
                sound.author = owner

    if not preview_seed_url:
        return None

    match = FREESOUND_PREVIEW_RE.match(preview_seed_url)
    if not match:
        return None

    sound_id = int(sound.source_sound_id)
    bucket = sound_id // 1000
    token = match.group("token")
    quality = match.group("quality")
    inferred_url = f"https://cdn.freesound.org/previews/{bucket}/{sound_id}_{token}-{quality}.mp3"
    sound.preview_url = inferred_url
    return inferred_url


def _is_freesound_download_url(file_url: Optional[str]) -> bool:
    return bool(file_url and FREESOUND_DOWNLOAD_RE.match(file_url))


def _can_download_sound(sound: Sound) -> bool:
    if not sound.file_url:
        return False

    if sound.source == "freesound" or _is_freesound_download_url(sound.file_url):
        return False

    return True


@router.get("/", response_model=PaginatedResponse[SoundSummary])
def list_sounds(
    q: Optional[str] = Query(None, description="Free-text search query."),
    tags: Optional[List[str]] = Query(
        None,
        description="Tags to filter by (multi-value).",
    ),
    license: Optional[List[str]] = Query(
        None,
        alias="license",
        description="License labels to filter by, e.g. cc0, cc-by.",
    ),
    min_duration: Optional[float] = Query(None, ge=0),
    max_duration: Optional[float] = Query(None, ge=0),
    min_brightness: Optional[float] = Query(None, ge=0),
    max_brightness: Optional[float] = Query(None, ge=0),
    bpm_min: Optional[float] = Query(None, ge=0),
    bpm_max: Optional[float] = Query(None, ge=0),
    key: Optional[str] = Query(None),
    is_loop: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SoundSummary]:
    settings = get_settings()
    if page_size > settings.max_page_size:
        page_size = settings.max_page_size

    stmt, total = build_sound_search_query(
        db,
        q=q,
        tags=tags,
        license_labels=license,
        min_duration=min_duration,
        max_duration=max_duration,
        min_brightness=min_brightness,
        max_brightness=max_brightness,
        bpm_min=bpm_min,
        bpm_max=bpm_max,
        key=key,
        is_loop=is_loop,
    )

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(stmt).all()

    items: List[SoundSummary] = []
    for sound, features in rows:
        inferred_preview_url = _infer_freesound_preview_url(sound, db)
        items.append(
            SoundSummary(
                id=sound.id,
                name=sound.name,
                author=sound.author,
                duration_sec=sound.duration_sec,
                tags=sound.tags or [],
                license_label=sound.license_label,
                preview_url=inferred_preview_url,
                file_url=sound.file_url,
                source_page_url=normalize_freesound_source_page_url(
                    sound.source_page_url,
                    sound_id=sound.source_sound_id,
                    author=sound.author,
                ),
                can_preview=bool(inferred_preview_url),
                can_download=_can_download_sound(sound),
                brightness=(features.spectral_centroid if features else None),
                bpm=(features.bpm if features else None),
                key=(features.key if features else None),
            )
        )

    return PaginatedResponse[SoundSummary](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{sound_id}", response_model=SoundDetail)
def get_sound_detail(
    sound_id: int,
    db: Session = Depends(get_db),
) -> SoundDetail:
    stmt = (
        select(Sound, SoundFeatures)
        .outerjoin(SoundFeatures, Sound.id == SoundFeatures.sound_id)
        .where(Sound.id == sound_id)
    )
    row = db.execute(stmt).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Sound not found")

    sound, features = row
    features_schema: Optional[SoundFeaturesSchema] = None
    if features:
        features_schema = SoundFeaturesSchema(
            spectral_centroid=features.spectral_centroid,
            spectral_rolloff=features.spectral_rolloff,
            loudness_lufs=features.loudness_lufs,
            rms=features.rms,
            bpm=features.bpm,
            key=features.key,
            is_loop=features.is_loop,
        )

    return SoundDetail(
        id=sound.id,
        name=sound.name,
        description=sound.description,
        author=sound.author,
        duration_sec=sound.duration_sec,
        sample_rate=sound.sample_rate,
        channels=sound.channels,
        tags=sound.tags or [],
        license_url=sound.license_url,
        license_label=sound.license_label,
        source=sound.source,
        source_sound_id=sound.source_sound_id,
        source_page_url=normalize_freesound_source_page_url(
            sound.source_page_url,
            sound_id=sound.source_sound_id,
            author=sound.author,
        ),
        preview_url=sound.preview_url,
        file_url=sound.file_url,
        ingested_at=sound.ingested_at,
        updated_at=sound.updated_at,
        features=features_schema,
    )


@router.get("/{sound_id}/preview")
def stream_sound_preview(
    sound_id: int,
    db: Session = Depends(get_db),
):
    sound = db.get(Sound, sound_id)
    if sound is None:
        raise HTTPException(status_code=404, detail="Sound not found")

    inferred_preview_url = _infer_freesound_preview_url(sound, db)
    if inferred_preview_url:
        db.commit()
        return RedirectResponse(url=inferred_preview_url)

    if sound.preview_url:
        return RedirectResponse(url=sound.preview_url)

    if sound.source != "freesound":
        raise HTTPException(status_code=404, detail="No preview available for this source")

    settings = get_settings()
    if settings.freesound_api_token in ("...", "your_freesound_token_here"):
        raise HTTPException(
            status_code=503,
            detail="Freesound token is not configured on the backend",
        )

    try:
        payload = FreesoundClient.from_settings().get_sound(
            int(sound.source_sound_id),
            fields=["id", "previews", "download", "url", "username"],
        )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Preview lookup timed out upstream. Please try again in a moment.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Preview lookup failed upstream. Please try again in a moment.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Failed to fetch upstream metadata ({exc.response.status_code})",
        ) from exc

    preview_url = extract_preview_url(payload)
    if not preview_url:
        raise HTTPException(status_code=404, detail="No preview URL available for this sound")

    # Persist metadata so subsequent requests avoid upstream calls.
    sound.preview_url = preview_url
    sound.file_url = payload.get("download") or sound.file_url
    sound.author = extract_author(payload) or sound.author
    sound.source_page_url = normalize_freesound_source_page_url(
        payload.get("url") or sound.source_page_url,
        sound_id=sound.source_sound_id,
        author=sound.author,
    )
    db.commit()

    return RedirectResponse(url=preview_url)


@router.get("/{sound_id}/download")
def download_sound_file(
    sound_id: int,
    db: Session = Depends(get_db),
):
    sound = db.get(Sound, sound_id)
    if sound is None:
        raise HTTPException(status_code=404, detail="Sound not found")

    if not sound.file_url:
        raise HTTPException(status_code=404, detail="No downloadable file available for this sound")

    if not _can_download_sound(sound):
        raise HTTPException(
            status_code=503,
            detail="Original WAV downloads for Freesound require OAuth2 and are not available in this app yet.",
        )

    return RedirectResponse(url=sound.file_url)
