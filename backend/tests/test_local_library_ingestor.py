from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import BinaryExpression, BindParameter, BooleanClauseList

from app.ingestion.presets import local_library_ingestor
from app.ingestion.presets.base import (
    get_or_create_preset_pack,
    get_or_create_preset_source,
)
from app.models import IngestionRun, Preset, PresetFile, PresetPack, PresetSource


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
    if condition.operator is operators.is_:
        return left_value is right_value
    if condition.operator is operators.is_not:
        return left_value is not right_value

    raise AssertionError(f"Unsupported binary operator: {condition.operator}")


def _settings_for(tmp_path: Path):
    return SimpleNamespace(
        preset_local_roots=[str(tmp_path)],
        preset_file_extensions_allowlist=[".fxp", ".fxb", ".serumpreset", ".vital"],
    )


def _write_serum_fixture(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"HeaderData Macro 1 Macro 2 Filter FX OSC A OSC B TailData")


def _monkeypatch_ingestor(monkeypatch, session: FakeSession, tmp_path: Path):
    monkeypatch.setattr(local_library_ingestor, "SessionLocal", lambda: session)
    monkeypatch.setattr(local_library_ingestor, "get_settings", lambda: _settings_for(tmp_path))


def test_classify_local_preset_file_uses_bank_folder_and_nested_tags(tmp_path: Path):
    preset_path = tmp_path / "serum" / "My Bank" / "Warm Pads" / "Lead 01.fxp"
    _write_serum_fixture(preset_path)

    classified = local_library_ingestor.classify_local_preset_file(
        tmp_path,
        preset_path,
        {".fxp", ".serumpreset"},
    )

    assert classified.skip_reason is None
    assert classified.discovery is not None
    assert classified.discovery.bank_name == "My Bank"
    assert classified.discovery.bank_external_id == "local:serum:my-bank"
    assert classified.discovery.tags == ("my bank", "serum", "warm pads")


def test_get_or_create_preset_pack_upgrades_legacy_local_external_id():
    session = FakeSession()
    source = get_or_create_preset_source(
        session,
        key="local-filesystem",
        label="Local Filesystem",
        source_type="local",
    )
    legacy_pack = PresetPack(
        source_id=source.id,
        external_id="local:factory",
        name="Factory",
        synth_name="Serum",
    )
    session.add(legacy_pack)
    session.flush()

    pack = get_or_create_preset_pack(
        session,
        source=source,
        external_id="local:serum:factory",
        name="Factory",
        synth_name="Serum",
    )

    assert pack is legacy_pack
    assert legacy_pack.external_id == "local:serum:factory"


def test_ingest_local_presets_is_idempotent(monkeypatch, tmp_path: Path):
    preset_path = tmp_path / "serum" / "My Bank" / "Lead 01.fxp"
    _write_serum_fixture(preset_path)

    session = FakeSession()
    _monkeypatch_ingestor(monkeypatch, session, tmp_path)

    first = local_library_ingestor.ingest_local_presets()
    second = local_library_ingestor.ingest_local_presets()

    assert first["ingested_count"] == 1
    assert second["ingested_count"] == 1
    assert len(session.store[PresetSource]) == 1
    assert len(session.store[PresetPack]) == 1
    assert len(session.store[Preset]) == 1
    assert len(session.store[PresetFile]) == 1
    assert session.store[PresetPack][0].external_id == "local:serum:my-bank"
    assert len(session.store[IngestionRun]) == 2


def test_ingest_local_presets_keeps_duplicate_hashes_in_multiple_banks(monkeypatch, tmp_path: Path):
    _write_serum_fixture(tmp_path / "serum" / "Bank A" / "Lead 01.fxp")
    _write_serum_fixture(tmp_path / "serum" / "Bank B" / "Lead 01.fxp")

    session = FakeSession()
    _monkeypatch_ingestor(monkeypatch, session, tmp_path)

    result = local_library_ingestor.ingest_local_presets()

    assert result["ingested_count"] == 2
    assert len(session.store[PresetPack]) == 2
    assert len(session.store[PresetFile]) == 2
    assert len({preset_file.file_hash_sha256 for preset_file in session.store[PresetFile]}) == 1
    assert len({preset_file.preset_id for preset_file in session.store[PresetFile]}) == 2


def test_ingest_local_presets_reports_skips(monkeypatch, tmp_path: Path):
    _write_serum_fixture(tmp_path / "serum" / "My Bank" / "Lead 01.fxp")
    _write_serum_fixture(tmp_path / "serum" / "My Bank" / "Factory.fxb")
    unsupported = tmp_path / "vital" / "Factory" / "Patch.vital"
    unsupported.parent.mkdir(parents=True, exist_ok=True)
    unsupported.write_text("noop", encoding="utf-8")

    session = FakeSession()
    _monkeypatch_ingestor(monkeypatch, session, tmp_path)

    result = local_library_ingestor.ingest_local_presets()

    assert result["scanned_files"] == 3
    assert result["ingested_count"] == 1
    assert result["parse_failed_count"] == 0
    assert result["skipped_unsupported_synth_count"] == 1
    assert result["skipped_unsupported_extension_count"] == 1
