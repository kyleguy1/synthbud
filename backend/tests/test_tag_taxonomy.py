from datetime import UTC, datetime
from types import SimpleNamespace

from app.ingestion.backfill_tag_taxonomy import _backfill_records
from app.tag_taxonomy import build_tag_facets, canonicalize_tags, reconcile_tag_fields


def test_canonicalize_tags_normalizes_aliases_and_rejects_noise():
    assert canonicalize_tags(
        [
            "Warm Pads",
            "Pads",
            "LoFi",
            "232hz",
            "1:23",
            "v1.2",
            "808",
            "drum & bass",
        ]
    ) == ["bass", "pad", "warm", "lo-fi", "drum-and-bass"]


def test_build_tag_facets_groups_tags_by_category():
    facets = build_tag_facets(["Warm Pads", "LoFi", "Drum & Bass", "Aggressive"])

    assert facets == [
        {"key": "family", "label": "Family", "tags": []},
        {"key": "role", "label": "Role", "tags": ["pad"]},
        {"key": "timbre", "label": "Timbre", "tags": ["warm", "lo-fi"]},
        {"key": "mood", "label": "Mood / Style", "tags": ["aggressive"]},
        {"key": "genre", "label": "Genre", "tags": ["drum-and-bass"]},
    ]


def test_reconcile_tag_fields_preserves_raw_and_recomputes_canonical():
    raw_tags, canonical_tags = reconcile_tag_fields(
        raw_tags=None,
        existing_tags=["Warm Pads", "232hz", "Dubstep"],
    )

    assert raw_tags == ["Warm Pads", "232hz", "Dubstep"]
    assert canonical_tags == ["pad", "warm", "dubstep"]


def test_backfill_records_copies_legacy_tags_into_raw_tags():
    record = SimpleNamespace(
        raw_tags=None,
        tags=["Warm Pads", "Lead", "232hz"],
        updated_at=datetime(2020, 1, 1, tzinfo=UTC),
    )

    updated = _backfill_records([record])

    assert updated == 1
    assert record.raw_tags == ["Warm Pads", "Lead", "232hz"]
    assert record.tags == ["pad", "lead", "warm"]
