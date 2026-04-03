from collections import Counter
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Preset, PresetPack, PresetSource, Sound
from app.scrapers.presetshare import (
    list_supported_genre_names,
    list_supported_sound_type_names,
    list_supported_synth_names,
)


router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/tags", response_model=List[str])
def list_tags(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> List[str]:
    """
    Return the most frequent tags across all sounds.
    """
    rows = db.execute(select(Sound.tags).where(Sound.tags.isnot(None))).all()
    counter: Counter[str] = Counter()
    for (tags,) in rows:
        if not tags:
            continue
        counter.update([t for t in tags if t])
    return [tag for tag, _ in counter.most_common(limit)]


@router.get("/licenses")
def list_licenses() -> dict:
    """
    Return allowed license labels and URLs from configuration.
    """
    settings = get_settings()
    labels = {}
    for url in settings.license_allowlist_urls:
        label = settings.license_label_map.get(str(url), "UNKNOWN")
        labels[label] = str(url)
    return {"licenses": labels}


@router.get("/synths", response_model=List[str])
def list_synths(
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> List[str]:
    if source and source.strip().lower() == "presetshare":
        return list_supported_synth_names()

    stmt = (
        select(Preset.synth_name)
        .join(PresetPack, Preset.pack_id == PresetPack.id)
        .join(PresetSource, PresetPack.source_id == PresetSource.id)
        .where(Preset.synth_name.isnot(None))
        .distinct()
        .order_by(Preset.synth_name.asc())
    )
    if source:
        stmt = stmt.where(PresetSource.key == source)

    rows = db.execute(stmt).all()
    return [name for (name,) in rows if name]


@router.get("/preset-packs", response_model=List[str])
def list_preset_packs(
    limit: int = Query(100, ge=1, le=500),
    synth: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> List[str]:
    if source and source.strip().lower() == "presetshare":
        return []

    stmt = (
        select(PresetPack.name)
        .join(PresetSource, PresetPack.source_id == PresetSource.id)
        .where(PresetPack.name.isnot(None))
        .distinct()
        .order_by(PresetPack.name.asc())
        .limit(limit)
    )
    if synth:
        stmt = stmt.where(PresetPack.synth_name == synth)
    if source:
        stmt = stmt.where(PresetSource.key == source)

    rows = db.execute(stmt).all()
    return [name for (name,) in rows if name]


@router.get("/preset-genres", response_model=List[str])
def list_preset_genres(source: Optional[str] = Query(None)) -> List[str]:
    if source and source.strip().lower() == "presetshare":
        return list_supported_genre_names()
    return []


@router.get("/preset-types", response_model=List[str])
def list_preset_types(source: Optional[str] = Query(None)) -> List[str]:
    if source and source.strip().lower() == "presetshare":
        return list_supported_sound_type_names()
    return []


@router.get("/preset-tags", response_model=List[str])
def list_preset_tags(limit: int = 50, db: Session = Depends(get_db)) -> List[str]:
    rows = db.execute(select(Preset.tags).where(Preset.tags.isnot(None))).all()
    counter: Counter[str] = Counter()
    for (tags,) in rows:
        if not tags:
            continue
        counter.update([tag for tag in tags if tag])
    return [tag for tag, _ in counter.most_common(limit)]
