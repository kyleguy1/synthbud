from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any

from app.config import get_settings
from app.db import SessionLocal
from app.models import IngestionRun, IngestionStatusEnum, PresetParseStatusEnum, PresetVisibilityEnum
from app.scrapers.presetshare import PRESETSHARE_UPSTREAM_PAGE_SIZE, scrape_presets_page

from .base import (
    ParsedPreset,
    get_or_create_preset_pack,
    get_or_create_preset_source,
    upsert_preset_from_parse,
)


NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _normalize_identifier(value: str, *, fallback: str) -> str:
    normalized = NON_ALNUM_RE.sub("-", value.strip().lower()).strip("-")
    return normalized or fallback


def _build_pack_external_id(synth_name: str | None) -> str:
    return f"presetshare-index:{_normalize_identifier(synth_name or 'unknown', fallback='unknown')}"


def ingest_presetshare_index(max_pages: int = 10) -> dict[str, Any]:
    settings = get_settings()
    requested_pages = max(1, max_pages)

    scanned_pages = 0
    ingested_count = 0

    with SessionLocal() as db:
        run = IngestionRun(source="presetshare-index", started_at=datetime.now(UTC))
        db.add(run)
        db.flush()

        try:
            source = get_or_create_preset_source(
                db,
                key="presetshare-index",
                label="PresetShare Index",
                source_type="public",
                base_url=str(settings.presetshare_base_url),
            )

            for page in range(1, requested_pages + 1):
                items = scrape_presets_page(
                    page=page,
                    cache_ttl_seconds=settings.presetshare_cache_ttl_seconds,
                    min_request_interval_seconds=settings.presetshare_min_request_interval_seconds,
                )
                scanned_pages += 1
                if not items:
                    break

                for item in items:
                    synth_name = item.get("synth") or "Unknown"
                    pack = get_or_create_preset_pack(
                        db,
                        source=source,
                        external_id=_build_pack_external_id(synth_name),
                        name=f"{synth_name} Presets",
                        synth_name=synth_name,
                        source_url=str(settings.presetshare_base_url),
                        visibility=PresetVisibilityEnum.PUBLIC,
                        is_redistributable=True,
                        description="Indexed online preset metadata from PresetShare.",
                    )

                    raw_tags = [value for value in [item.get("genre"), item.get("soundType")] if value]
                    parsed = ParsedPreset(
                        preset_name=item.get("name") or f"Preset {item.get('id') or 'unknown'}",
                        synth_name=synth_name,
                        author=item.get("author"),
                        parse_status=PresetParseStatusEnum.PARTIAL,
                        raw_payload=dict(item),
                    )
                    upsert_preset_from_parse(
                        db,
                        pack=pack,
                        preset_key=str(item.get("id") or f"{page}:{ingested_count}"),
                        parsed=parsed,
                        raw_tags=raw_tags,
                        source_url=item.get("url"),
                        parser_version="presetshare-index-0.1",
                    )
                    ingested_count += 1

                if len(items) < PRESETSHARE_UPSTREAM_PAGE_SIZE:
                    break

            run.status = IngestionStatusEnum.SUCCESS
            run.finished_at = datetime.now(UTC)
            run.details = {
                "requested_pages": requested_pages,
                "scanned_pages": scanned_pages,
                "ingested_count": ingested_count,
            }
            db.commit()
        except Exception as exc:  # pragma: no cover
            db.rollback()
            run.status = IngestionStatusEnum.ERROR
            run.finished_at = datetime.now(UTC)
            run.details = {
                "error": str(exc),
                "requested_pages": requested_pages,
                "scanned_pages": scanned_pages,
                "ingested_count": ingested_count,
            }
            db.add(run)
            db.commit()
            raise

    return {
        "source": "presetshare-index",
        "requested_pages": requested_pages,
        "scanned_pages": scanned_pages,
        "ingested_count": ingested_count,
    }


if __name__ == "__main__":
    result = ingest_presetshare_index()
    print(result)
