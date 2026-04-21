import re
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audio import (
    build_local_waveform_source_key,
    build_remote_waveform_source_key,
    compute_waveform_peaks,
    get_audio_duration_sec,
    load_audio_file_to_array,
    load_audio_url_to_array,
    resample_waveform_peaks,
)
from app.config import get_settings
from app.db import get_db
from app.ingestion.freesound_client import FreesoundClient
from app.ingestion.freesound_ingestor import (
    extract_author,
    extract_preview_url,
    normalize_freesound_source_page_url,
)
from app.models import Sound, SoundFeatures
from app.schemas import (
    PaginatedResponse,
    SoundDetail,
    SoundFeatures as SoundFeaturesSchema,
    SoundSummary,
    SoundWaveform,
)
from app.services.search import build_sound_search_query


router = APIRouter(prefix="/api/sounds", tags=["sounds"])

FREESOUND_OWNER_RE = re.compile(r"/people/(?P<owner>[^/]+)/sounds/")
FREESOUND_PREVIEW_RE = re.compile(
    r"^https://cdn\.freesound\.org/previews/(?P<bucket>\d+)/(?P<sound_id>\d+)_(?P<token>\d+)-(?P<quality>hq|lq)\.mp3$"
)
FREESOUND_DOWNLOAD_RE = re.compile(r"^https://freesound\.org/apiv2/sounds/\d+/download/?$")
DEFAULT_WAVEFORM_BINS = 72
MAX_WAVEFORM_BINS = 256


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


def _resolve_local_sound_path(sound: Sound) -> Optional[Path]:
    if sound.source != "local-filesystem" or not sound.file_url:
        return None

    path = Path(sound.file_url).expanduser().resolve()
    settings = get_settings()
    allowed_roots = [Path(root).expanduser().resolve() for root in settings.sample_local_roots]
    if not any(path.is_relative_to(root) for root in allowed_roots):
        return None
    if not path.exists() or not path.is_file():
        return None
    return path


def _resolve_or_fetch_preview_url(sound: Sound, db: Session) -> Optional[str]:
    existing_preview_url = sound.preview_url
    inferred_preview_url = _infer_freesound_preview_url(sound, db)
    if inferred_preview_url:
        if existing_preview_url != inferred_preview_url:
            db.commit()
        return inferred_preview_url

    if sound.preview_url:
        return sound.preview_url

    if sound.source != "freesound":
        return None

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

    preview_url = extract_preview_url(payload)
    if not preview_url:
        return None

    sound.preview_url = preview_url
    sound.file_url = payload.get("download") or sound.file_url
    sound.author = extract_author(payload) or sound.author
    sound.source_page_url = normalize_freesound_source_page_url(
        payload.get("url") or sound.source_page_url,
        sound_id=sound.source_sound_id,
        author=sound.author,
    )
    db.commit()
    return preview_url


@lru_cache(maxsize=256)
def _build_local_waveform(file_path: str, source_key: str, bins: int, target_sr: int) -> tuple[float, tuple[float, ...]]:
    del source_key
    audio = load_audio_file_to_array(Path(file_path), target_sr)
    duration_sec = get_audio_duration_sec(audio, target_sr)
    return duration_sec, tuple(compute_waveform_peaks(audio, bins))


@lru_cache(maxsize=256)
def _build_remote_waveform(preview_url: str, source_key: str, bins: int, target_sr: int) -> tuple[float, tuple[float, ...]]:
    del source_key
    audio = load_audio_url_to_array(preview_url, target_sr)
    duration_sec = get_audio_duration_sec(audio, target_sr)
    return duration_sec, tuple(compute_waveform_peaks(audio, bins))


def _clear_waveform_cache() -> None:
    _build_local_waveform.cache_clear()
    _build_remote_waveform.cache_clear()


def _get_default_waveform_bins() -> int:
    configured_bins = getattr(get_settings(), "waveform_default_bins", DEFAULT_WAVEFORM_BINS)
    return min(MAX_WAVEFORM_BINS, max(16, configured_bins or DEFAULT_WAVEFORM_BINS))


def _ensure_sound_features_instance(db: Session, sound: Sound) -> SoundFeatures:
    features = getattr(sound, "features", None)
    if features is None:
        features = SoundFeatures(sound_id=sound.id)
        setattr(sound, "features", features)
        db.add(features)
    return features


def _get_cached_waveform(sound: Sound, source_key: str, bins: int) -> Optional[tuple[Optional[float], list[float]]]:
    features = getattr(sound, "features", None)
    if features is None:
        return None

    cached_peaks = getattr(features, "waveform_peaks", None)
    cached_bins = getattr(features, "waveform_bins", None)
    cached_source_key = getattr(features, "waveform_source_key", None)
    if not cached_peaks or not cached_bins or cached_source_key != source_key:
        return None

    duration_sec = getattr(features, "waveform_duration_sec", None)
    if duration_sec is None:
        duration_sec = sound.duration_sec

    peaks = (
        [float(peak) for peak in cached_peaks]
        if cached_bins == bins
        else resample_waveform_peaks(cached_peaks, bins)
    )
    return duration_sec, peaks


def _persist_waveform(
    db: Session,
    sound: Sound,
    *,
    source_key: str,
    peaks: tuple[float, ...],
    bins: int,
    duration_sec: float,
) -> None:
    features = _ensure_sound_features_instance(db, sound)
    features.waveform_peaks = [float(peak) for peak in peaks]
    features.waveform_bins = bins
    features.waveform_duration_sec = duration_sec
    features.waveform_source_key = source_key
    features.waveform_analyzed_at = datetime.now(UTC)
    db.commit()


def _can_preview_sound(sound: Sound, preview_url: Optional[str]) -> bool:
    if preview_url:
        return True
    return _resolve_local_sound_path(sound) is not None


def _can_download_sound(sound: Sound) -> bool:
    if not sound.file_url:
        return False

    if sound.source == "local-filesystem":
        return _resolve_local_sound_path(sound) is not None

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
                can_preview=_can_preview_sound(sound, inferred_preview_url),
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


@router.get("/{sound_id}/waveform", response_model=SoundWaveform)
def get_sound_waveform(
    sound_id: int,
    bins: int = Query(DEFAULT_WAVEFORM_BINS, ge=1, le=MAX_WAVEFORM_BINS),
    db: Session = Depends(get_db),
) -> SoundWaveform:
    sound = db.get(Sound, sound_id)
    if sound is None:
        raise HTTPException(status_code=404, detail="Sound not found")

    target_sr = get_settings().feature_sample_rate
    default_bins = _get_default_waveform_bins()
    local_sound_path = _resolve_local_sound_path(sound)
    source_key: Optional[str] = None
    preview_url: Optional[str] = None

    if local_sound_path is not None:
        source_key = build_local_waveform_source_key(local_sound_path)
    else:
        preview_url = _resolve_or_fetch_preview_url(sound, db)
        if not preview_url:
            raise HTTPException(status_code=404, detail="No preview available for waveform extraction")
        source_key = build_remote_waveform_source_key(preview_url)

    cached_waveform = _get_cached_waveform(sound, source_key, bins)
    if cached_waveform is not None:
        cached_duration_sec, cached_peaks = cached_waveform
        return SoundWaveform(
            sound_id=sound.id,
            bins=bins,
            duration_sec=sound.duration_sec if sound.duration_sec is not None else cached_duration_sec,
            peaks=cached_peaks,
        )

    try:
        if local_sound_path is not None:
            duration_sec, peaks = _build_local_waveform(
                str(local_sound_path),
                source_key,
                default_bins,
                target_sr,
            )
        else:
            duration_sec, peaks = _build_remote_waveform(preview_url, source_key, default_bins, target_sr)
    except HTTPException:
        raise
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail="Waveform generation timed out while fetching preview audio.",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Waveform generation failed while fetching preview audio.",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail="Preview audio could not be decoded for waveform extraction.",
        ) from exc

    _persist_waveform(
        db,
        sound,
        source_key=source_key,
        peaks=peaks,
        bins=default_bins,
        duration_sec=duration_sec,
    )

    requested_peaks = list(peaks) if bins == default_bins else resample_waveform_peaks(peaks, bins)
    return SoundWaveform(
        sound_id=sound.id,
        bins=bins,
        duration_sec=sound.duration_sec if sound.duration_sec is not None else duration_sec,
        peaks=requested_peaks,
    )


@router.get("/{sound_id}/preview")
def stream_sound_preview(
    sound_id: int,
    db: Session = Depends(get_db),
):
    sound = db.get(Sound, sound_id)
    if sound is None:
        raise HTTPException(status_code=404, detail="Sound not found")

    local_sound_path = _resolve_local_sound_path(sound)
    if local_sound_path is not None:
        return FileResponse(path=local_sound_path, filename=local_sound_path.name)

    preview_url = _resolve_or_fetch_preview_url(sound, db)
    if not preview_url:
        if sound.source != "freesound":
            raise HTTPException(status_code=404, detail="No preview available for this source")
        raise HTTPException(status_code=404, detail="No preview URL available for this sound")
    return RedirectResponse(url=preview_url)


@router.get("/{sound_id}/download")
def download_sound_file(
    sound_id: int,
    db: Session = Depends(get_db),
):
    sound = db.get(Sound, sound_id)
    if sound is None:
        raise HTTPException(status_code=404, detail="Sound not found")

    local_sound_path = _resolve_local_sound_path(sound)
    if local_sound_path is not None:
        return FileResponse(path=local_sound_path, filename=local_sound_path.name)

    if not sound.file_url:
        raise HTTPException(status_code=404, detail="No downloadable file available for this sound")

    if not _can_download_sound(sound):
        raise HTTPException(
            status_code=503,
            detail="Original WAV downloads for Freesound require OAuth2 and are not available in this app yet.",
        )

    return RedirectResponse(url=sound.file_url)
