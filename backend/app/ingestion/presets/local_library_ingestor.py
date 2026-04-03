from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable
import re

from app.config import get_settings
from app.db import SessionLocal
from app.models import IngestionRun, IngestionStatusEnum, PresetParseStatusEnum, PresetVisibilityEnum
from .base import (
    get_or_create_preset_pack,
    get_or_create_preset_source,
    sha256_file,
    upsert_preset_file,
    upsert_preset_from_parse,
)
from .registry import PresetSynthHandler, resolve_synth_handler


UNSORTED_BANK_NAME = "Unsorted"
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
SEPARATOR_RE = re.compile(r"[_\-]+")
WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class LocalPresetDiscovery:
    root: Path
    file_path: Path
    relative_path: Path
    synth_handler: PresetSynthHandler
    bank_name: str
    bank_external_id: str
    nested_tag_parts: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class LocalFileClassification:
    discovery: LocalPresetDiscovery | None = None
    skip_reason: str | None = None


def _iter_local_files(roots: Iterable[Path]) -> Iterable[tuple[Path, Path]]:
    for root in roots:
        if not root.exists():
            continue
        for file_path in sorted(root.rglob("*")):
            if file_path.is_file():
                yield root, file_path


def _normalize_identifier(value: str, *, fallback: str) -> str:
    normalized = NON_ALNUM_RE.sub("-", value.strip().lower()).strip("-")
    return normalized or fallback


def _normalize_tag(value: str) -> str:
    compacted = SEPARATOR_RE.sub(" ", value.strip())
    normalized = WHITESPACE_RE.sub(" ", compacted).strip().lower()
    return normalized


def _build_bank_external_id(synth_key: str, bank_name: str) -> str:
    return f"local:{synth_key}:{_normalize_identifier(bank_name, fallback='unsorted')}"


def _build_search_tags(
    synth_handler: PresetSynthHandler,
    bank_name: str,
    nested_parts: Iterable[str],
) -> tuple[str, ...]:
    tags: list[str] = []
    for value in [bank_name, synth_handler.synth_key, *nested_parts]:
        normalized = _normalize_tag(value)
        if normalized and normalized not in tags:
            tags.append(normalized)
    return tuple(tags)


def classify_local_preset_file(
    root: Path,
    file_path: Path,
    extensions_allowlist: set[str] | None = None,
) -> LocalFileClassification:
    relative_path = file_path.resolve().relative_to(root)
    parts = relative_path.parts
    if len(parts) < 2:
        return LocalFileClassification(skip_reason="unsupported_synth")

    synth_handler = resolve_synth_handler(parts[0])
    if synth_handler is None:
        return LocalFileClassification(skip_reason="unsupported_synth")

    extension = file_path.suffix.lower()
    configured_extensions = {value.lower() for value in (extensions_allowlist or set())}
    if configured_extensions and extension not in configured_extensions:
        return LocalFileClassification(skip_reason="unsupported_extension")
    if not synth_handler.supports_extension(extension):
        return LocalFileClassification(skip_reason="unsupported_extension")

    bank_name = UNSORTED_BANK_NAME if len(parts) == 2 else parts[1]
    nested_parts = tuple(parts[2:-1]) if len(parts) > 3 else ()
    return LocalFileClassification(
        discovery=LocalPresetDiscovery(
            root=root,
            file_path=file_path,
            relative_path=relative_path,
            synth_handler=synth_handler,
            bank_name=bank_name,
            bank_external_id=_build_bank_external_id(synth_handler.synth_key, bank_name),
            nested_tag_parts=nested_parts,
            tags=_build_search_tags(synth_handler, bank_name, nested_parts),
        )
    )


def ingest_local_presets(limit: int | None = None) -> dict:
    settings = get_settings()
    roots = [Path(path).expanduser().resolve() for path in settings.preset_local_roots]
    allowlist = {ext.lower() for ext in settings.preset_file_extensions_allowlist}

    scanned_files = 0
    ingested = 0
    parse_failed = 0
    skipped_unsupported_synth = 0
    skipped_unsupported_extension = 0
    eligible_files_seen = 0

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

            for root, file_path in _iter_local_files(roots):
                scanned_files += 1
                classification = classify_local_preset_file(root, file_path, allowlist)
                if classification.discovery is None:
                    if classification.skip_reason == "unsupported_synth":
                        skipped_unsupported_synth += 1
                    elif classification.skip_reason == "unsupported_extension":
                        skipped_unsupported_extension += 1
                    continue

                eligible_files_seen += 1
                if limit is not None and eligible_files_seen > limit:
                    break

                discovery = classification.discovery
                file_hash = sha256_file(file_path)
                parsed = discovery.synth_handler.parser(file_path)
                if parsed.parse_status == PresetParseStatusEnum.FAILED:
                    parse_failed += 1

                pack = get_or_create_preset_pack(
                    db,
                    source=source,
                    external_id=discovery.bank_external_id,
                    name=discovery.bank_name,
                    synth_name=(
                        parsed.synth_name
                        if parsed.synth_name != "Unknown"
                        else discovery.synth_handler.display_name
                    ),
                    synth_vendor=parsed.synth_vendor or discovery.synth_handler.vendor,
                    visibility=PresetVisibilityEnum.PRIVATE,
                    is_redistributable=False,
                )

                preset = upsert_preset_from_parse(
                    db,
                    pack=pack,
                    preset_key=file_hash[:24],
                    parsed=parsed,
                    tags=discovery.tags,
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
                "scanned_files": scanned_files,
                "ingested_count": ingested,
                "parse_failed_count": parse_failed,
                "skipped_unsupported_synth_count": skipped_unsupported_synth,
                "skipped_unsupported_extension_count": skipped_unsupported_extension,
            }
            db.commit()
        except Exception as exc:  # pragma: no cover
            db.rollback()
            run.status = IngestionStatusEnum.ERROR
            run.finished_at = datetime.now(UTC)
            run.details = {
                "error": str(exc),
                "roots": [str(path) for path in roots],
                "scanned_files": scanned_files,
                "ingested_count": ingested,
                "parse_failed_count": parse_failed,
                "skipped_unsupported_synth_count": skipped_unsupported_synth,
                "skipped_unsupported_extension_count": skipped_unsupported_extension,
            }
            db.add(run)
            db.commit()
            raise

    return {
        "ingested_count": ingested,
        "parse_failed_count": parse_failed,
        "roots": [str(path) for path in roots],
        "scanned_files": scanned_files,
        "skipped_unsupported_synth_count": skipped_unsupported_synth,
        "skipped_unsupported_extension_count": skipped_unsupported_extension,
    }


if __name__ == "__main__":
    result = ingest_local_presets()
    print(result)
