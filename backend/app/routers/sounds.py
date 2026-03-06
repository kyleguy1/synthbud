from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Sound, SoundFeatures
from app.schemas import PaginatedResponse, SoundDetail, SoundFeatures as SoundFeaturesSchema, SoundSummary
from app.services.search import build_sound_search_query


router = APIRouter(prefix="/api/sounds", tags=["sounds"])


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
        items.append(
            SoundSummary(
                id=sound.id,
                name=sound.name,
                author=sound.author,
                duration_sec=sound.duration_sec,
                tags=sound.tags or [],
                license_label=sound.license_label,
                preview_url=sound.preview_url,
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
        source_page_url=sound.source_page_url,
        preview_url=sound.preview_url,
        file_url=sound.file_url,
        ingested_at=sound.ingested_at,
        updated_at=sound.updated_at,
        features=features_schema,
    )

