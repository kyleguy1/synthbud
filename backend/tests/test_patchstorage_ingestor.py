from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace

from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import BinaryExpression, BindParameter, BooleanClauseList

from app.ingestion.presets import patchstorage_ingestor
from app.models import IngestionRun, Preset, PresetPack, PresetSource


# ---------------------------------------------------------------------------
# Fake DB session (same pattern as test_presetshare_index_ingestor.py)
# ---------------------------------------------------------------------------

class FakeQuery:
    def __init__(self, session: "FakeSession", model, conditions=None):
        self.session = session
        self.model = model
        self.conditions = list(conditions or [])

    def filter(self, *conditions):
        return FakeQuery(self.session, self.model, [*self.conditions, *conditions])

    def first(self):
        for obj in self.session.store[self.model]:
            if all(_matches(obj, condition) for condition in self.conditions):
                return obj
        return None


class FakeSession:
    def __init__(self):
        self.store = defaultdict(list)
        self.next_ids = defaultdict(int)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add(self, obj):
        if obj not in self.store[type(obj)]:
            self.store[type(obj)].append(obj)
        self._assign_id(obj)

    def flush(self):
        for objects in self.store.values():
            for obj in objects:
                self._assign_id(obj)

    def query(self, model):
        return FakeQuery(self, model)

    def commit(self):
        self.flush()

    def rollback(self):
        pass

    def _assign_id(self, obj):
        if not hasattr(obj, "id") or getattr(obj, "id", None) is not None:
            return
        model = type(obj)
        self.next_ids[model] += 1
        setattr(obj, "id", self.next_ids[model])


def _extract_bound_value(value):
    if isinstance(value, BindParameter):
        return value.value
    return getattr(value, "value", value)


def _matches(obj, condition) -> bool:
    if isinstance(condition, BooleanClauseList):
        if condition.operator is operators.and_:
            return all(_matches(obj, clause) for clause in condition.clauses)
        if condition.operator is operators.or_:
            return any(_matches(obj, clause) for clause in condition.clauses)
        raise AssertionError(f"Unsupported boolean operator: {condition.operator}")

    if not isinstance(condition, BinaryExpression):
        raise AssertionError(f"Unsupported filter condition: {condition!r}")

    left_key = getattr(condition.left, "key", None)
    assert left_key is not None, f"Missing left key for condition: {condition!r}"
    left_value = getattr(obj, left_key)
    right_value = _extract_bound_value(condition.right)

    if condition.operator is operators.eq:
        return left_value == right_value
    if condition.operator is operators.ne:
        return left_value != right_value

    raise AssertionError(f"Unsupported binary operator: {condition.operator}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _fake_settings():
    return SimpleNamespace(
        patchstorage_cache_ttl_seconds=60,
        patchstorage_min_request_interval_seconds=0.0,
    )


def _sample_items():
    return {
        1: [
            {
                "id": 5001,
                "title": "Deep Sub",
                "excerpt": "A heavy sub bass",
                "author_name": "bassmaker",
                "platform_names": ["Vital"],
                "category_names": ["Preset"],
                "tag_names": ["bass", "sub"],
                "license_name": "CC0",
                "license_slug": "cc0",
                "date_created": "2025-06-01",
                "url": "https://patchstorage.com/deep-sub/",
                "download_count": 300,
                "view_count": 1200,
                "source": "patchstorage",
            },
            {
                "id": 5002,
                "title": "Ethereal Pad",
                "excerpt": "Ambient texture",
                "author_name": "padcrafter",
                "platform_names": ["Vital"],
                "category_names": ["Preset"],
                "tag_names": ["pad", "ambient"],
                "license_name": "CC-BY",
                "license_slug": "cc-by",
                "date_created": "2025-05-20",
                "url": "https://patchstorage.com/ethereal-pad/",
                "download_count": 180,
                "view_count": 900,
                "source": "patchstorage",
            },
        ],
    }


def _monkeypatch_ingestor(monkeypatch, session, items):
    monkeypatch.setattr(patchstorage_ingestor, "SessionLocal", lambda: session)
    monkeypatch.setattr(patchstorage_ingestor, "get_settings", _fake_settings)
    monkeypatch.setattr(
        patchstorage_ingestor,
        "resolve_platform_id",
        lambda name, **kw: 9999,
    )
    monkeypatch.setattr(
        patchstorage_ingestor,
        "fetch_patches_page",
        lambda **kwargs: (items.get(kwargs["page"], []), bool(items.get(kwargs["page"] + 1))),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_ingest_patchstorage_creates_presets(monkeypatch):
    session = FakeSession()
    items = _sample_items()
    _monkeypatch_ingestor(monkeypatch, session, items)

    result = patchstorage_ingestor.ingest_patchstorage(synth_name="vital", max_pages=5)

    assert result["source"] == "patchstorage-index"
    assert result["synth_filter"] == "vital"
    assert result["ingested_count"] == 2
    assert result["scanned_pages"] == 1
    assert len(session.store[PresetSource]) == 1
    assert len(session.store[Preset]) == 2
    assert len(session.store[IngestionRun]) == 1


def test_ingest_patchstorage_is_idempotent(monkeypatch):
    session = FakeSession()
    items = _sample_items()
    _monkeypatch_ingestor(monkeypatch, session, items)

    first = patchstorage_ingestor.ingest_patchstorage(synth_name="vital", max_pages=5)
    second = patchstorage_ingestor.ingest_patchstorage(synth_name="vital", max_pages=5)

    assert first["ingested_count"] == 2
    assert second["ingested_count"] == 2
    assert len(session.store[PresetSource]) == 1
    assert len(session.store[Preset]) == 2
    assert len(session.store[IngestionRun]) == 2


def test_ingest_patchstorage_one_pack_per_patch(monkeypatch):
    session = FakeSession()
    items = _sample_items()
    _monkeypatch_ingestor(monkeypatch, session, items)

    patchstorage_ingestor.ingest_patchstorage(synth_name="vital", max_pages=5)

    # Each Patchstorage patch gets its own pack
    assert len(session.store[PresetPack]) == 2
    external_ids = {pack.external_id for pack in session.store[PresetPack]}
    assert external_ids == {"patchstorage:5001", "patchstorage:5002"}


def test_ingest_patchstorage_preserves_author_and_tags(monkeypatch):
    session = FakeSession()
    items = _sample_items()
    _monkeypatch_ingestor(monkeypatch, session, items)

    patchstorage_ingestor.ingest_patchstorage(synth_name="vital", max_pages=5)

    authors = {preset.author for preset in session.store[Preset]}
    assert authors == {"bassmaker", "padcrafter"}

    all_tags = set()
    for preset in session.store[Preset]:
        if preset.tags:
            all_tags.update(preset.tags)
    assert "bass" in all_tags
    assert "pad" in all_tags


def test_ingest_patchstorage_sets_redistributable(monkeypatch):
    session = FakeSession()
    items = _sample_items()
    _monkeypatch_ingestor(monkeypatch, session, items)

    patchstorage_ingestor.ingest_patchstorage(synth_name="vital", max_pages=5)

    for pack in session.store[PresetPack]:
        assert pack.is_redistributable is True
