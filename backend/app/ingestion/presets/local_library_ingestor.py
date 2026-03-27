from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from app.config import get_settings
from app.db import SessionLocal
from app.models import IngestionRun, IngestionStatusEnum, PresetVisibilityEnum
from .base import (
    get_or_create_preset_pack,
    get_or_create_preset_source,
    sha256_file,
    upsert_preset_file,
    upsert_preset_from_parse,
)
from .serum_parser import parse_serum_preset


def _iter_local_files(roots: Iterable[Path], extensions_allowlist: set[str]) -> Iterable[Path]:
    for root in roots:
        if not root.exists():
            continue
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in extensions_allowlist:
                continue
            yield file_path


def ingest_local_presets(limit: int | None = None) -> dict:
    settings = get_settings()
    roots = [Path(path).expanduser().resolve() for path in settings.preset_local_roots]
    allowlist = {ext.lower() for ext in settings.preset_file_extensions_allowlist}

    ingested = 0
    parse_failed = 0

    with SessionLocal() as db:
        run = IngestionRun(source="preset-local", started_at=datetime.now(UTC))
        db.add(run)
        db.flush()

        try:
            source = get_or_create_preset_source(
                db,
                key="local-filesystem",
                label="Local Filesystem",
                source_type="local",
            )

            for idx, file_path in enumerate(_iter_local_files(roots, allowlist), start=1):
                if limit is not None and idx > limit:
                    break

                file_hash = sha256_file(file_path)
                relative_parent = file_path.parent.name or "Local Pack"
                parsed = parse_serum_preset(file_path)
                if parsed.parse_status.value == "failed":
                    parse_failed += 1

                pack = get_or_create_preset_pack(
                    db,
                    source=source,
                    external_id=f"local:{relative_parent.lower()}",
                    name=relative_parent,
                    synth_name=parsed.synth_name if parsed.synth_name != "Unknown" else "Serum",
                    synth_vendor=parsed.synth_vendor,
                    visibility=PresetVisibilityEnum.PRIVATE,
                    is_redistributable=False,
                )

                preset = upsert_preset_from_parse(
                    db,
                    pack=pack,
                    preset_key=file_hash[:24],
                    parsed=parsed,
                    tags=[pack.name, parsed.synth_name.lower()],
                    source_url=None,
                )
                upsert_preset_file(
                    db,
                    preset=preset,
                    file_name=file_path.name,
                    file_path=str(file_path),
                    extension=file_path.suffix.lower() or None,
                    size_bytes=file_path.stat().st_size,
                    file_hash_sha256=file_hash,
                    is_local=True,
                )
                ingested += 1

            run.status = IngestionStatusEnum.SUCCESS
            run.finished_at = datetime.now(UTC)
            run.details = {
                "roots": [str(path) for path in roots],
                "ingested_count": ingested,
                "parse_failed_count": parse_failed,
            }
            db.commit()
        except Exception as exc:  # pragma: no cover
            db.rollback()
            run.status = IngestionStatusEnum.ERROR
            run.finished_at = datetime.now(UTC)
            run.details = {
                "error": str(exc),
                "ingested_count": ingested,
                "parse_failed_count": parse_failed,
            }
            db.add(run)
            db.commit()
            raise

    return {
        "ingested_count": ingested,
        "parse_failed_count": parse_failed,
        "roots": [str(path) for path in roots],
    }


if __name__ == "__main__":
    result = ingest_local_presets()
    print(result)
