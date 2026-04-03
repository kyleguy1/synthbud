from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Optional
import hashlib
import re

from sqlalchemy.orm import Session

from app.models import (
    Preset,
    PresetFile,
    PresetPack,
    PresetParameters,
    PresetParseStatusEnum,
    PresetSource,
    PresetVisibilityEnum,
)


SERUM_FILE_HINT_RE = re.compile(r"(serum|\.fxp$|\.serumpreset$)", re.IGNORECASE)
LOCAL_EXTERNAL_ID_RE = re.compile(r"^local:[a-z0-9-]+:.+$")


@dataclass
class ParsedPreset:
    preset_name: str
    synth_name: str
    synth_vendor: Optional[str] = None
    parse_status: PresetParseStatusEnum = PresetParseStatusEnum.PARTIAL
    parse_error: Optional[str] = None
    raw_payload: Optional[dict] = None
    macro_names: list[str] = field(default_factory=list)
    macro_values: Optional[dict] = None
    osc_count: Optional[int] = None
    fx_enabled: Optional[bool] = None
    filter_enabled: Optional[bool] = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def looks_like_serum_file(path: Path) -> bool:
    return bool(SERUM_FILE_HINT_RE.search(path.name))


def get_or_create_preset_source(
    db: Session,
    *,
    key: str,
    label: str,
    source_type: str,
    base_url: str | None = None,
) -> PresetSource:
    source = db.query(PresetSource).filter(PresetSource.key == key).first()
    if source:
        if base_url and source.base_url != base_url:
            source.base_url = base_url
            source.updated_at = datetime.now(UTC)
        return source

    source = PresetSource(
        key=key,
        label=label,
        source_type=source_type,
        base_url=base_url,
    )
    db.add(source)
    db.flush()
    return source


def get_or_create_preset_pack(
    db: Session,
    *,
    source: PresetSource,
    external_id: str | None,
    name: str,
    synth_name: str,
    synth_vendor: str | None = None,
    author: str | None = None,
    source_url: str | None = None,
    license_label: str | None = None,
    license_url: str | None = None,
    visibility: PresetVisibilityEnum = PresetVisibilityEnum.PRIVATE,
    is_redistributable: bool = False,
    description: str | None = None,
) -> PresetPack:
    query = db.query(PresetPack).filter(PresetPack.source_id == source.id)
    if external_id:
        query = query.filter(PresetPack.external_id == external_id)
    else:
        query = query.filter(PresetPack.name == name, PresetPack.synth_name == synth_name)

    pack = query.first()
    if (
        pack is None
        and external_id
        and source.source_type == "local"
        and LOCAL_EXTERNAL_ID_RE.match(external_id)
    ):
        legacy_pack = (
            db.query(PresetPack)
            .filter(
                PresetPack.source_id == source.id,
                PresetPack.name == name,
                PresetPack.synth_name == synth_name,
            )
            .first()
        )
        if legacy_pack is not None and legacy_pack.external_id != external_id:
            legacy_pack.external_id = external_id
            legacy_pack.updated_at = datetime.now(UTC)
            pack = legacy_pack

    if pack is None:
        pack = PresetPack(
            source_id=source.id,
            external_id=external_id,
            name=name,
            author=author,
            description=description,
            synth_name=synth_name,
            synth_vendor=synth_vendor,
            source_url=source_url,
            license_label=license_label,
            license_url=license_url,
            visibility=visibility,
            is_redistributable=is_redistributable,
        )
        db.add(pack)
        db.flush()
        return pack

    pack.author = author or pack.author
    pack.description = description or pack.description
    pack.synth_name = synth_name
    pack.synth_vendor = synth_vendor or pack.synth_vendor
    pack.source_url = source_url or pack.source_url
    pack.license_label = license_label or pack.license_label
    pack.license_url = license_url or pack.license_url
    pack.visibility = visibility
    pack.is_redistributable = is_redistributable
    pack.updated_at = datetime.now(UTC)
    return pack


def upsert_preset_from_parse(
    db: Session,
    *,
    pack: PresetPack,
    preset_key: str,
    parsed: ParsedPreset,
    tags: Iterable[str] | None = None,
    source_url: str | None = None,
    parser_version: str = "serum-mvp-0.1",
) -> Preset:
    preset = (
        db.query(Preset)
        .filter(Preset.pack_id == pack.id, Preset.preset_key == preset_key)
        .first()
    )
    normalized_tags = [t.strip() for t in (tags or []) if t and t.strip()]

    if preset is None:
        preset = Preset(
            pack_id=pack.id,
            preset_key=preset_key,
            name=parsed.preset_name,
            author=pack.author,
            tags=normalized_tags or None,
            synth_name=parsed.synth_name,
            synth_vendor=parsed.synth_vendor or pack.synth_vendor,
            visibility=pack.visibility,
            is_redistributable=pack.is_redistributable,
            source_url=source_url or pack.source_url,
            parse_status=parsed.parse_status,
            parse_error=parsed.parse_error,
            parser_version=parser_version,
        )
        db.add(preset)
        db.flush()
    else:
        preset.name = parsed.preset_name
        preset.author = preset.author or pack.author
        preset.tags = normalized_tags or preset.tags
        preset.synth_name = parsed.synth_name
        preset.synth_vendor = parsed.synth_vendor or preset.synth_vendor
        preset.visibility = pack.visibility
        preset.is_redistributable = pack.is_redistributable
        preset.source_url = source_url or preset.source_url or pack.source_url
        preset.parse_status = parsed.parse_status
        preset.parse_error = parsed.parse_error
        preset.parser_version = parser_version
        preset.updated_at = datetime.now(UTC)

    if preset.parameters is None:
        preset.parameters = PresetParameters(preset_id=preset.id)
        db.add(preset.parameters)

    preset.parameters.raw_payload = parsed.raw_payload
    preset.parameters.macro_names = parsed.macro_names or None
    preset.parameters.macro_values = parsed.macro_values
    preset.parameters.osc_count = parsed.osc_count
    preset.parameters.fx_enabled = parsed.fx_enabled
    preset.parameters.filter_enabled = parsed.filter_enabled
    preset.parameters.analyzed_at = datetime.now(UTC)

    return preset


def upsert_preset_file(
    db: Session,
    *,
    preset: Preset,
    file_name: str,
    file_path: str | None,
    extension: str | None,
    size_bytes: int | None,
    file_hash_sha256: str,
    is_local: bool,
) -> PresetFile:
    preset_file = (
        db.query(PresetFile)
        .filter(
            PresetFile.preset_id == preset.id,
            PresetFile.file_hash_sha256 == file_hash_sha256,
        )
        .first()
    )
    if preset_file is None:
        preset_file = PresetFile(
            preset_id=preset.id,
            file_name=file_name,
            file_path=file_path,
            extension=extension,
            size_bytes=size_bytes,
            file_hash_sha256=file_hash_sha256,
            is_local=is_local,
        )
        db.add(preset_file)
        return preset_file

    preset_file.preset_id = preset.id
    preset_file.file_name = file_name
    preset_file.file_path = file_path
    preset_file.extension = extension
    preset_file.size_bytes = size_bytes
    preset_file.is_local = is_local
    return preset_file
