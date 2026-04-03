from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Preset, PresetPack, PresetParameters, PresetSource, PresetVisibilityEnum
from app.ingestion.presets.presetshare_index_ingestor import ingest_presetshare_index
from app.scrapers.presetshare import (
    clear_cache as clear_presetshare_cache,
    build_cache_key as build_presetshare_cache_key,
    resolve_genre_id,
    resolve_sound_type_id,
    resolve_synth_id,
    scrape_presets_window,
)
from app.schemas import PaginatedResponse, PresetDetail, PresetPackSummary, PresetSummary


router = APIRouter(prefix="/api/presets", tags=["presets"])


def _build_preset_summary(
    *,
    preset: Preset,
    pack: PresetPack,
    preset_source: PresetSource,
    parameters: Optional[PresetParameters] = None,
) -> PresetSummary:
    raw_payload = parameters.raw_payload if parameters and parameters.raw_payload else {}

    return PresetSummary(
        id=preset.id,
        name=preset.name,
        author=preset.author,
        author_url=raw_payload.get("authorUrl"),
        synth_name=preset.synth_name,
        synth_vendor=preset.synth_vendor,
        tags=preset.tags or [],
        visibility=preset.visibility.value,
        is_redistributable=preset.is_redistributable,
        parse_status=preset.parse_status.value,
        source_url=preset.source_url,
        source_key=preset_source.key,
        posted_label=raw_payload.get("datePosted"),
        like_count=raw_payload.get("likes"),
        download_count=raw_payload.get("downloads"),
        comment_count=raw_payload.get("comments"),
        pack=PresetPackSummary(
            id=pack.id,
            name=pack.name,
            author=pack.author,
            synth_name=pack.synth_name,
            synth_vendor=pack.synth_vendor,
            source_url=pack.source_url,
            license_label=pack.license_label,
            is_redistributable=pack.is_redistributable,
            visibility=pack.visibility.value,
            source_key=preset_source.key,
        ),
    )


@router.get("/", response_model=PaginatedResponse[PresetSummary])
def list_presets(
    q: Optional[str] = Query(None, description="Free-text query for preset name/author."),
    synth: Optional[List[str]] = Query(None, description="Synth names, e.g. serum, vital."),
    genre: Optional[str] = Query(None, description="Genre name, e.g. Dubstep."),
    type: Optional[str] = Query(None, description="Sound type name, e.g. Lead."),
    source: Optional[str] = Query(None, description="Preset source provider key."),
    pack: Optional[List[str]] = Query(None, description="Pack name(s)."),
    author: Optional[List[str]] = Query(None, description="Author name(s)."),
    visibility: Optional[str] = Query(None, pattern="^(public|private)$"),
    redistributable: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[PresetSummary]:
    if source and source.strip().lower() == "presetshare":
        settings = get_settings()
        synth_name = synth[0] if synth else None
        synth_id = resolve_synth_id(synth_name)
        genre_id = resolve_genre_id(genre)
        sound_type_id = resolve_sound_type_id(type)

        scraped, has_next = scrape_presets_window(
            instrument=synth_id,
            genre=genre_id,
            sound_type=sound_type_id,
            page=page,
            limit=page_size,
            cache_ttl_seconds=settings.presetshare_cache_ttl_seconds,
            min_request_interval_seconds=settings.presetshare_min_request_interval_seconds,
        )
        if q:
            q_lower = q.lower()
            scraped = [
                item
                for item in scraped
                if q_lower in (item.get("name") or "").lower()
                or q_lower in (item.get("author") or "").lower()
            ]

        items: List[PresetSummary] = []
        for item in scraped:
            fallback_id = int(item["id"]) if item["id"].isdigit() else 0
            pack_name = f'{item.get("synth") or "PresetShare"} Presets'
            items.append(
                PresetSummary(
                    id=fallback_id,
                    name=item.get("name") or f"Preset {item['id']}",
                    author=item.get("author"),
                    author_url=item.get("authorUrl"),
                    synth_name=item.get("synth") or "Unknown",
                    synth_vendor=None,
                    tags=[value for value in [item.get("genre"), item.get("soundType")] if value],
                    visibility="public",
                    is_redistributable=True,
                    parse_status="success",
                    source_url=item.get("url"),
                    source_key="presetshare",
                    posted_label=item.get("datePosted"),
                    like_count=item.get("likes"),
                    download_count=item.get("downloads"),
                    comment_count=item.get("comments"),
                    pack=PresetPackSummary(
                        id=fallback_id,
                        name=pack_name,
                        author=item.get("author"),
                        synth_name=item.get("synth") or "Unknown",
                        synth_vendor=None,
                        source_url=item.get("url"),
                        license_label=None,
                        is_redistributable=True,
                        visibility="public",
                        source_key="presetshare",
                    ),
                )
            )
        total = ((page - 1) * page_size) + len(items) + (1 if has_next else 0)
        return PaginatedResponse[PresetSummary](
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            has_next=has_next,
        )

    stmt = (
        select(Preset, PresetPack, PresetSource, PresetParameters)
        .join(PresetPack, Preset.pack_id == PresetPack.id)
        .join(PresetSource, PresetPack.source_id == PresetSource.id)
        .outerjoin(PresetParameters, Preset.id == PresetParameters.preset_id)
    )
    conditions = []

    if q:
        pattern = f"%{q.lower()}%"
        conditions.append(
            or_(
                func.lower(Preset.name).like(pattern),
                func.lower(func.coalesce(Preset.author, "")).like(pattern),
                func.lower(PresetPack.name).like(pattern),
            )
        )
    if synth:
        conditions.append(Preset.synth_name.in_(synth))
    if genre:
        conditions.append(Preset.tags.any(genre))
    if type:
        conditions.append(Preset.tags.any(type))
    if pack:
        conditions.append(PresetPack.name.in_(pack))
    if author:
        conditions.append(Preset.author.in_(author))
    if visibility:
        conditions.append(Preset.visibility == PresetVisibilityEnum(visibility))
    if redistributable is not None:
        conditions.append(Preset.is_redistributable.is_(redistributable))
    if source:
        conditions.append(PresetSource.key == source)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()

    items = [
        _build_preset_summary(
            preset=preset,
            pack=pack,
            preset_source=preset_source,
            parameters=parameters,
        )
        for preset, pack, preset_source, parameters in rows
    ]

    return PaginatedResponse[PresetSummary](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get("/{preset_id}", response_model=PresetDetail)
def get_preset_detail(
    preset_id: int,
    db: Session = Depends(get_db),
) -> PresetDetail:
    row = db.execute(
        select(Preset, PresetPack, PresetParameters, PresetSource)
        .join(PresetPack, Preset.pack_id == PresetPack.id)
        .join(PresetSource, PresetPack.source_id == PresetSource.id)
        .outerjoin(PresetParameters, Preset.id == PresetParameters.preset_id)
        .where(Preset.id == preset_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Preset not found")

    preset, pack, parameters, preset_source = row
    summary = _build_preset_summary(
        preset=preset,
        pack=pack,
        preset_source=preset_source,
        parameters=parameters,
    )
    return PresetDetail(
        **summary.model_dump(),
        parse_error=preset.parse_error,
        parser_version=preset.parser_version,
        imported_at=preset.imported_at,
        updated_at=preset.updated_at,
        raw_payload=(parameters.raw_payload if parameters else None),
        macro_names=(parameters.macro_names if parameters and parameters.macro_names else []),
        macro_values=(parameters.macro_values if parameters else None),
        osc_count=(parameters.osc_count if parameters else None),
        fx_enabled=(parameters.fx_enabled if parameters else None),
        filter_enabled=(parameters.filter_enabled if parameters else None),
    )


@router.post("/sync")
def sync_presets(
    source: str = Query("presetshare-index"),
    max_pages: int = Query(10, ge=1, le=250),
) -> dict:
    normalized_source = source.strip().lower()
    if normalized_source != "presetshare-index":
        raise HTTPException(status_code=400, detail="Only presetshare-index sync is supported.")

    return ingest_presetshare_index(max_pages=max_pages)


@router.post("/cache-bust")
def clear_presets_cache(
    source: str = Query("presetshare"),
    instrument: Optional[int] = Query(None),
    genre: Optional[int] = Query(None),
    type: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
) -> dict:
    if source.strip().lower() != "presetshare":
        raise HTTPException(status_code=400, detail="Only presetshare cache busting is supported.")

    removed = 0
    if instrument is None and genre is None and type is None:
        removed = clear_presetshare_cache()
    else:
        key = build_presetshare_cache_key(
            instrument=instrument,
            genre=genre,
            sound_type=type,
            page=page,
        )
        removed = clear_presetshare_cache(key)
    return {"source": "presetshare", "removed": removed}
