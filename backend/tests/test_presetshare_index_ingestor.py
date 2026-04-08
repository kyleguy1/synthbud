from collections import defaultdict
from types import SimpleNamespace

from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import BinaryExpression, BindParameter, BooleanClauseList

from app.ingestion.presets import presetshare_index_ingestor
from app.models import IngestionRun, Preset, PresetPack, PresetSource


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


def test_ingest_presetshare_index_is_idempotent(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(presetshare_index_ingestor, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        presetshare_index_ingestor,
        "get_settings",
        lambda: SimpleNamespace(
            presetshare_base_url="https://presetshare.com",
            presetshare_cache_ttl_seconds=60,
            presetshare_min_request_interval_seconds=0.0,
        ),
    )

    pages = {
        1: [
            {
                "id": "101",
                "name": "Neuro Lead",
                "url": "https://presetshare.com/p101",
                "synth": "Vital",
                "genre": "Dubstep",
                "soundType": "Lead",
                "author": "presetuser",
                "authorUrl": "https://presetshare.com/@presetuser",
                "likes": 10,
                "downloads": 200,
                "comments": 3,
                "datePosted": "Today",
            },
            {
                "id": "102",
                "name": "Air Pad",
                "url": "https://presetshare.com/p102",
                "synth": "Serum",
                "genre": "Synthwave",
                "soundType": "Pad",
                "author": "anotheruser",
                "authorUrl": "https://presetshare.com/@anotheruser",
                "likes": 4,
                "downloads": 50,
                "comments": 0,
                "datePosted": "Yesterday",
            },
        ]
    }
    monkeypatch.setattr(
        presetshare_index_ingestor,
        "scrape_presets_page",
        lambda **kwargs: pages.get(kwargs["page"], []),
    )

    first = presetshare_index_ingestor.ingest_presetshare_index(max_pages=3)
    second = presetshare_index_ingestor.ingest_presetshare_index(max_pages=3)

    assert first["ingested_count"] == 2
    assert second["ingested_count"] == 2
    assert len(session.store[PresetSource]) == 1
    assert len(session.store[PresetPack]) == 2
    assert len(session.store[Preset]) == 2
    assert len(session.store[IngestionRun]) == 2
    assert {pack.external_id for pack in session.store[PresetPack]} == {
        "presetshare-index:serum",
        "presetshare-index:vital",
    }
    assert {preset.author for preset in session.store[Preset]} == {"presetuser", "anotheruser"}
    tags_by_name = {preset.name: preset.tags for preset in session.store[Preset]}
    raw_tags_by_name = {preset.name: preset.raw_tags for preset in session.store[Preset]}
    assert tags_by_name["Neuro Lead"] == ["lead", "dubstep"]
    assert raw_tags_by_name["Air Pad"] == ["Synthwave", "Pad"]
