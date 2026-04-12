from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import json

from app.config import get_settings
from app.db import SessionLocal
from app.models import IngestionRun, IngestionStatusEnum, PresetParseStatusEnum, PresetVisibilityEnum
from .base import get_or_create_preset_pack, get_or_create_preset_source, upsert_preset_from_parse, ParsedPreset


def _is_source_allowed(url: str | None, allowlist: set[str]) -> bool:
    if not url:
        return False
    host = (urlparse(url).hostname or "").lower()
    return any(host == allowed or host.endswith(f".{allowed}") for allowed in allowlist)


def _iter_catalog_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend(sorted(root.rglob("*.json")))
    return files


def ingest_public_catalog(limit_files: int | None = None) -> dict[str, Any]:
    settings = get_settings()
    roots = [Path(path).expanduser().resolve() for path in settings.preset_public_metadata_roots]
    allowlist = {domain.lower() for domain in settings.preset_public_source_allowlist}
    files = _iter_catalog_files(roots)
    if limit_files is not None:
        files = files[:limit_files]

    ingested_presets = 0
    skipped_sources = 0

    with SessionLocal() as db:
        run = IngestionRun(source="preset-public", started_at=datetime.now(UTC))
        db.add(run)
        db.flush()
        try:
            source = get_or_create_preset_source(
                db,
                key="public-catalog",
                label="Public Preset Catalog",
                source_type="public",
            )

            for file_path in files:
                payload = json.loads(file_path.read_text(encoding="utf-8"))
                packs = payload.get("packs") or []
                for pack_payload in packs:
                    source_url = pack_payload.get("source_url")
                    if not _is_source_allowed(source_url, allowlist):
                        skipped_sources += 1
                        continue

                    pack = get_or_create_preset_pack(
                        db,
                        source=source,
                        external_id=pack_payload.get("external_id") or file_path.stem,
                        name=pack_payload.get("name") or "Unnamed Pack",
                        author=pack_payload.get("author"),
                        description=pack_payload.get("description"),
                        synth_name=pack_payload.get("synth_name") or "Serum",
                        synth_vendor=pack_payload.get("synth_vendor"),
                        source_url=source_url,
                        license_label=pack_payload.get("license_label"),
                        license_url=pack_payload.get("license_url"),
                        visibility=PresetVisibilityEnum.PUBLIC,
                        is_redistributable=bool(pack_payload.get("is_redistributable", False)),
                    )

                    for preset_payload in pack_payload.get("presets") or []:
                        parsed = ParsedPreset(
                            preset_name=preset_payload.get("name") or "Unnamed Preset",
                            synth_name=pack.synth_name,
                            synth_vendor=pack.synth_vendor,
                            parse_status=PresetParseStatusEnum.PARTIAL,
                            raw_payload=preset_payload.get("raw_payload"),
                            macro_names=preset_payload.get("macro_names") or [],
                            macro_values=preset_payload.get("macro_values"),
                            osc_count=preset_payload.get("osc_count"),
                            fx_enabled=preset_payload.get("fx_enabled"),
                            filter_enabled=preset_payload.get("filter_enabled"),
                        )
                        upsert_preset_from_parse(
                            db,
                            pack=pack,
                            preset_key=str(preset_payload.get("preset_key") or preset_payload.get("name") or "preset"),
                            parsed=parsed,
                            raw_tags=preset_payload.get("tags") or [],
                            source_url=preset_payload.get("source_url") or pack.source_url,
                        )
                        ingested_presets += 1

            run.status = IngestionStatusEnum.SUCCESS
            run.finished_at = datetime.now(UTC)
            run.details = {
                "ingested_presets": ingested_presets,
                "catalog_files": [str(path) for path in files],
                "skipped_sources": skipped_sources,
            }
            db.commit()
        except Exception as exc:  # pragma: no cover
            db.rollback()
            run.status = IngestionStatusEnum.ERROR
            run.finished_at = datetime.now(UTC)
            run.details = {
                "error": str(exc),
                "ingested_presets": ingested_presets,
                "skipped_sources": skipped_sources,
            }
            db.add(run)
            db.commit()
            raise

    return {
        "ingested_presets": ingested_presets,
        "skipped_sources": skipped_sources,
    }


if __name__ == "__main__":
    result = ingest_public_catalog()
    print(result)
