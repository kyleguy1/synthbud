from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable, TypeVar

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Preset, Sound
from app.tag_taxonomy import reconcile_tag_fields


ModelWithTags = TypeVar("ModelWithTags", Sound, Preset)


def _backfill_records(records: Iterable[ModelWithTags]) -> int:
    updated = 0
    for record in records:
        raw_tags, canonical_tags = reconcile_tag_fields(
            raw_tags=getattr(record, "raw_tags", None),
            existing_tags=getattr(record, "tags", None),
        )
        if getattr(record, "raw_tags", None) == raw_tags and getattr(record, "tags", None) == canonical_tags:
            continue
        record.raw_tags = raw_tags
        record.tags = canonical_tags
        if hasattr(record, "updated_at"):
            record.updated_at = datetime.now(UTC)
        updated += 1
    return updated


def backfill_canonical_tags() -> dict[str, int]:
    with SessionLocal() as db:
        sounds = db.execute(select(Sound)).scalars().all()
        presets = db.execute(select(Preset)).scalars().all()

        sound_updates = _backfill_records(sounds)
        preset_updates = _backfill_records(presets)
        db.commit()

    return {
        "sound_updates": sound_updates,
        "preset_updates": preset_updates,
    }


if __name__ == "__main__":
    print(backfill_canonical_tags())
