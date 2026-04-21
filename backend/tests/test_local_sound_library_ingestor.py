from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

from app.audio import build_local_waveform_source_key
from app.ingestion import local_sound_library_ingestor
from app.ingestion.local_sound_library_ingestor import classify_local_sound_file
from app.models import IngestionRun, Sound
from app.tag_taxonomy import reconcile_tag_fields


def test_classify_local_sound_file_builds_raw_tags_and_canonical_tags(tmp_path: Path):
    sample_path = tmp_path / "Drums" / "Warm_Pads" / "Lead-01.wav"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_bytes(b"fake")

    discovery = classify_local_sound_file(tmp_path, sample_path, {".wav"})

    assert discovery is not None
    assert discovery.raw_tags == ("lead 01", "drums", "warm pads")

    raw_tags, canonical_tags = reconcile_tag_fields(raw_tags=discovery.raw_tags)
    assert raw_tags == ["lead 01", "drums", "warm pads"]
    assert canonical_tags == ["drum", "pad", "lead", "warm"]

class FakeQuery:
    def __init__(self, session, source=None, source_sound_id=None):
        self.session = session
        self.source = source
        self.source_sound_id = source_sound_id

    def filter(self, *conditions):
        source = self.source
        source_sound_id = self.source_sound_id
        for condition in conditions:
            left_key = getattr(condition.left, "key", None)
            right_value = getattr(condition.right, "value", None)
            if left_key == "source":
                source = right_value
            if left_key == "source_sound_id":
                source_sound_id = right_value
        return FakeQuery(self.session, source=source, source_sound_id=source_sound_id)

    def first(self):
        for sound in self.session.store[Sound]:
            if self.source is not None and sound.source != self.source:
                continue
            if self.source_sound_id is not None and sound.source_sound_id != self.source_sound_id:
                continue
            return sound
        return None


class _NestedTransaction:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


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
        return FakeQuery(self)

    def begin_nested(self):
        return _NestedTransaction()

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


def test_ingest_local_sounds_populates_persisted_waveform_cache(monkeypatch, tmp_path: Path):
    sample_root = tmp_path / "samples"
    sample_root.mkdir()
    sample_file = sample_root / "Lead-01.wav"
    sample_file.write_bytes(b"stub")

    session = FakeSession()
    fake_sf = SimpleNamespace(
        info=lambda _path: SimpleNamespace(duration=1.5, samplerate=44100, channels=2)
    )

    monkeypatch.setattr(local_sound_library_ingestor, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        local_sound_library_ingestor,
        "get_settings",
        lambda: SimpleNamespace(
            sample_local_roots=[str(sample_root)],
            sample_file_extensions_allowlist=[".wav"],
            feature_sample_rate=8000,
            waveform_default_bins=16,
        ),
    )
    monkeypatch.setattr(
        local_sound_library_ingestor,
        "_load_audio_dependencies",
        lambda: (fake_sf, lambda _audio, _sr: {"spectral_centroid": 555.0}),
    )
    monkeypatch.setattr(
        local_sound_library_ingestor,
        "_analyze_audio_file",
        lambda _path, _sr, _bins: (
            {"spectral_centroid": 555.0},
            [round(index / 16, 6) for index in range(1, 17)],
            0.5,
        ),
    )

    result = local_sound_library_ingestor.ingest_local_sounds(limit=1)

    assert result["ingested_count"] == 1
    assert len(session.store[Sound]) == 1
    assert len(session.store[IngestionRun]) == 1

    sound = session.store[Sound][0]
    assert sound.features is not None
    assert sound.features.waveform_peaks == [round(index / 16, 6) for index in range(1, 17)]
    assert sound.features.waveform_bins == 16
    assert sound.features.waveform_duration_sec == 1.5
    assert sound.features.waveform_source_key == build_local_waveform_source_key(sample_file)
    assert sound.features.waveform_analyzed_at is not None
    assert sound.features.analyzed_at is not None
    assert sound.features.spectral_centroid == 555.0
