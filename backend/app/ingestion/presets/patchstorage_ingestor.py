from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.config import get_settings
from app.db import SessionLocal
from app.models import IngestionRun, IngestionStatusEnum, PresetParseStatusEnum, PresetVisibilityEnum
from app.scrapers.patchstorage import (
    DEFAULT_PER_PAGE,
    fetch_patches_page,
    is_redistributable,
    resolve_platform_id,
)

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


def _build_pack_external_id(patch_id: int) -> str:
    return f"patchstorage:{patch_id}"


def _primary_platform(platform_names: list[str], synth_filter: str) -> str:
    """Return the best platform name, preferring the one matching synth_filter."""
    filter_lower = synth_filter.lower()
    for name in platform_names:
        if name.lower() == filter_lower:
            return name
    return platform_names[0] if platform_names else synth_filter.title()


def ingest_patchstorage(
    synth_name: str = "vital",
    max_pages: int = 20,
) -> dict[str, Any]:
    settings = get_settings()
    requested_pages = max(1, max_pages)

    scanned_pages = 0
    ingested_count = 0
    skipped_count = 0

    with SessionLocal() as db:
        run = IngestionRun(source="patchstorage-index", started_at=datetime.now(UTC))
        db.add(run)
        db.flush()

        try:
            source = get_or_create_preset_source(
                db,
                key="patchstorage-index",
                label="Patchstorage Index",
                source_type="public",
                base_url="https://patchstorage.com",
            )

            platform_id = resolve_platform_id(
                synth_name,
                min_request_interval_seconds=settings.patchstorage_min_request_interval_seconds,
            )

            for page in range(1, requested_pages + 1):
                items, has_next = fetch_patches_page(
                    platform_id=platform_id,
                    page=page,
                    per_page=DEFAULT_PER_PAGE,
                    cache_ttl_seconds=settings.patchstorage_cache_ttl_seconds,
                    min_request_interval_seconds=settings.patchstorage_min_request_interval_seconds,
                )
                scanned_pages += 1
                if not items:
                    break

                for item in items:
                    if not item["id"]:
                        skipped_count += 1
                        continue

                    platform = _primary_platform(item["platform_names"], synth_name)
                    redist = is_redistributable(item["license_slug"])

                    pack = get_or_create_preset_pack(
                        db,
                        source=source,
                        external_id=_build_pack_external_id(item["id"]),
                        name=item["title"],
                        synth_name=platform,
                        author=item["author_name"],
                        source_url=item["url"],
                        license_label=item["license_name"],
                        visibility=PresetVisibilityEnum.PUBLIC,
                        is_redistributable=redist,
                        description=item["excerpt"] or None,
                    )

                    tags = [
                        t
                        for t in item["category_names"] + item["tag_names"]
                        if t and t.strip()
                    ]

                    parsed = ParsedPreset(
                        preset_name=item["title"],
                        synth_name=platform,
                        author=item["author_name"],
                        parse_status=PresetParseStatusEnum.PARTIAL,
                        raw_payload={
                            "parser": "patchstorage-metadata-0.1",
                            "patch_id": item["id"],
                            "download_count": item["download_count"],
                            "view_count": item["view_count"],
                            "date_created": item["date_created"],
                            "license_slug": item["license_slug"],
                        },
                    )

                    upsert_preset_from_parse(
                        db,
                        pack=pack,
                        preset_key=str(item["id"]),
                        parsed=parsed,
                        tags=tags,
                        source_url=item["url"],
                        parser_version="patchstorage-metadata-0.1",
                    )
                    ingested_count += 1

                if not has_next:
                    break

            run.status = IngestionStatusEnum.SUCCESS
            run.finished_at = datetime.now(UTC)
            run.details = {
                "synth_filter": synth_name,
                "platform_id": platform_id,
                "requested_pages": requested_pages,
                "scanned_pages": scanned_pages,
                "ingested_count": ingested_count,
                "skipped_count": skipped_count,
            }
            db.commit()
        except Exception as exc:  # pragma: no cover
            db.rollback()
            run.status = IngestionStatusEnum.ERROR
            run.finished_at = datetime.now(UTC)
            run.details = {
                "error": str(exc),
                "synth_filter": synth_name,
                "platform_id": platform_id if "platform_id" in dir() else None,
                "requested_pages": requested_pages,
                "scanned_pages": scanned_pages,
                "ingested_count": ingested_count,
                "skipped_count": skipped_count,
            }
            db.add(run)
            db.commit()
            raise

    return {
        "source": "patchstorage-index",
        "synth_filter": synth_name,
        "platform_id": platform_id,
        "requested_pages": requested_pages,
        "scanned_pages": scanned_pages,
        "ingested_count": ingested_count,
        "skipped_count": skipped_count,
    }


if __name__ == "__main__":
    result = ingest_patchstorage()
    print(result)
