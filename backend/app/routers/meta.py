from collections import Counter
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Preset, PresetPack, PresetSource, Sound
from app.schemas import TagFacet
from app.scrapers.presetshare import (
    list_supported_genre_names,
    list_supported_sound_type_names,
    list_supported_synth_names,
)
from app.tag_taxonomy import build_tag_facets, canonicalize_tags


router = APIRouter(prefix="/api/meta", tags=["meta"])


def _count_tags(tag_rows: list[tuple[list[str] | None]], limit: int) -> list[str]:
    counter: Counter[str] = Counter()
    for (tags,) in tag_rows:
        if not tags:
            continue
        counter.update(canonicalize_tags(tags))
    return [tag for tag, _ in counter.most_common(limit)]


def _values_for_facets(tag_rows: list[tuple[list[str] | None]]) -> list[str]:
    values: list[str] = []
    for (tags,) in tag_rows:
        if not tags:
            continue
        values.extend([tag for tag in tags if tag])
    return values


@router.get("/tags", response_model=List[str])
def list_tags(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> List[str]:
    """
    Return the most frequent tags across all sounds.
    """
    rows = db.execute(select(Sound.tags).where(Sound.tags.isnot(None))).all()
    return _count_tags(rows, limit)


@router.get("/tag-facets", response_model=List[TagFacet])
def list_tag_facets(db: Session = Depends(get_db)) -> List[TagFacet]:
    rows = db.execute(select(Sound.tags).where(Sound.tags.isnot(None))).all()
    return [TagFacet(**facet) for facet in build_tag_facets(_values_for_facets(rows))]


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
    normalized_source = source.strip().lower() if source else None
    if normalized_source == "presetshare":
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
    normalized_source = source.strip().lower() if source else None
    if normalized_source in {"presetshare", "presetshare-index"}:
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
    normalized_source = source.strip().lower() if source else None
    if normalized_source in {"presetshare", "presetshare-index"}:
        return list_supported_genre_names()
    return []


@router.get("/preset-types", response_model=List[str])
def list_preset_types(source: Optional[str] = Query(None)) -> List[str]:
    normalized_source = source.strip().lower() if source else None
    if normalized_source in {"presetshare", "presetshare-index"}:
        return list_supported_sound_type_names()
    return []


@router.get("/preset-tags", response_model=List[str])
def list_preset_tags(
    limit: int = 50,
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> List[str]:
    normalized_source = source.strip().lower() if source else None
    if normalized_source in {"presetshare", "presetshare-index"}:
        return canonicalize_tags([*list_supported_genre_names(), *list_supported_sound_type_names()])[:limit]

    stmt = select(Preset.tags).where(Preset.tags.isnot(None))
    if source:
        stmt = (
            select(Preset.tags)
            .join(PresetPack, Preset.pack_id == PresetPack.id)
            .join(PresetSource, PresetPack.source_id == PresetSource.id)
            .where(Preset.tags.isnot(None), PresetSource.key == source)
        )

    rows = db.execute(stmt).all()
    return _count_tags(rows, limit)


@router.get("/preset-tag-facets", response_model=List[TagFacet])
def list_preset_tag_facets(
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> List[TagFacet]:
    normalized_source = source.strip().lower() if source else None
    if normalized_source in {"presetshare", "presetshare-index"}:
        return [
            TagFacet(**facet)
            for facet in build_tag_facets([*list_supported_genre_names(), *list_supported_sound_type_names()])
        ]

    stmt = select(Preset.tags).where(Preset.tags.isnot(None))
    if source:
        stmt = (
            select(Preset.tags)
            .join(PresetPack, Preset.pack_id == PresetPack.id)
            .join(PresetSource, PresetPack.source_id == PresetSource.id)
            .where(Preset.tags.isnot(None), PresetSource.key == source)
        )
    rows = db.execute(stmt).all()
    return [TagFacet(**facet) for facet in build_tag_facets(_values_for_facets(rows))]
