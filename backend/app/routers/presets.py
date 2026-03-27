from typing import List, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Preset, PresetPack, PresetParameters, PresetVisibilityEnum
from app.schemas import PaginatedResponse, PresetDetail, PresetPackSummary, PresetSummary


router = APIRouter(prefix="/api/presets", tags=["presets"])


@router.get("/", response_model=PaginatedResponse[PresetSummary])
def list_presets(
    q: Optional[str] = Query(None, description="Free-text query for preset name/author."),
    synth: Optional[List[str]] = Query(None, description="Synth names, e.g. serum, vital."),
    pack: Optional[List[str]] = Query(None, description="Pack name(s)."),
    author: Optional[List[str]] = Query(None, description="Author name(s)."),
    visibility: Optional[str] = Query(None, pattern="^(public|private)$"),
    redistributable: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedResponse[PresetSummary]:
    stmt = select(Preset, PresetPack).join(PresetPack, Preset.pack_id == PresetPack.id)
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
    if pack:
        conditions.append(PresetPack.name.in_(pack))
    if author:
        conditions.append(Preset.author.in_(author))
    if visibility:
        conditions.append(Preset.visibility == PresetVisibilityEnum(visibility))
    if redistributable is not None:
        conditions.append(Preset.is_redistributable.is_(redistributable))

    if conditions:
        stmt = stmt.where(and_(*conditions))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()

    items = [
        PresetSummary(
            id=preset.id,
            name=preset.name,
            author=preset.author,
            synth_name=preset.synth_name,
            synth_vendor=preset.synth_vendor,
            tags=preset.tags or [],
            visibility=preset.visibility.value,
            is_redistributable=preset.is_redistributable,
            parse_status=preset.parse_status.value,
            source_url=preset.source_url,
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
            ),
        )
        for preset, pack in rows
    ]

    return PaginatedResponse[PresetSummary](items=items, total=total, page=page, page_size=page_size)


@router.get("/{preset_id}", response_model=PresetDetail)
def get_preset_detail(
    preset_id: int,
    db: Session = Depends(get_db),
) -> PresetDetail:
    row = db.execute(
        select(Preset, PresetPack, PresetParameters)
        .join(PresetPack, Preset.pack_id == PresetPack.id)
        .outerjoin(PresetParameters, Preset.id == PresetParameters.preset_id)
        .where(Preset.id == preset_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Preset not found")

    preset, pack, parameters = row
    return PresetDetail(
        id=preset.id,
        name=preset.name,
        author=preset.author,
        synth_name=preset.synth_name,
        synth_vendor=preset.synth_vendor,
        tags=preset.tags or [],
        visibility=preset.visibility.value,
        is_redistributable=preset.is_redistributable,
        parse_status=preset.parse_status.value,
        source_url=preset.source_url,
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
        ),
    )
