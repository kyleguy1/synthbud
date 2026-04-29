from types import SimpleNamespace

import numpy as np

from app.audio import build_remote_waveform_source_key
from app.ingestion import feature_extractor
from app.models import SoundFeatures


class DummyQuery:
    def __init__(self, sounds):
        self._sounds = sounds

    def outerjoin(self, *_args, **_kwargs):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self._sounds)


class DummySession:
    def __init__(self, sounds):
        self._sounds = sounds
        self.commit_count = 0
        self.rollback_count = 0
        self.added = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def query(self, *_args, **_kwargs):
        return DummyQuery(self._sounds)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def test_process_pending_sounds_populates_waveform_cache(monkeypatch):
    sound = SimpleNamespace(
        id=11,
        preview_url="https://cdn.example.com/previews/11.mp3",
        duration_sec=None,
        tags=["Loop"],
        features=SoundFeatures(sound_id=11),
    )
    session = DummySession([sound])

    monkeypatch.setattr(feature_extractor, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        feature_extractor,
        "get_settings",
        lambda: SimpleNamespace(feature_sample_rate=4, feature_batch_size=4, waveform_default_bins=72),
    )
    monkeypatch.setattr(
        feature_extractor,
        "_download_audio_to_array",
        lambda url, sr: np.array([0.0, 0.5, -1.0, 0.25], dtype=np.float32),
    )
    monkeypatch.setattr(
        feature_extractor,
        "_compute_features",
        lambda y, sr: {"spectral_centroid": 2400.0, "bpm": 120.0},
    )
    monkeypatch.setattr(
        feature_extractor,
        "compute_waveform_peaks",
        lambda audio, bins: [0.1, 0.6, 1.0],
    )

    feature_extractor.process_pending_sounds(batch_size=1)

    assert sound.features.spectral_centroid == 2400.0
    assert sound.features.bpm == 120.0
    assert sound.features.is_loop is True
    assert sound.features.waveform_peaks == [0.1, 0.6, 1.0]
    assert sound.features.waveform_bins == 72
    assert sound.features.waveform_duration_sec == 1.0
    assert sound.features.waveform_source_key == build_remote_waveform_source_key(sound.preview_url)
    assert sound.features.waveform_analyzed_at is not None
    assert sound.features.analyzed_at is not None
    assert session.commit_count == 1
    assert session.rollback_count == 0
