import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.audio import build_local_waveform_source_key, build_remote_waveform_source_key
from app.config import get_settings
from app.main import app
from app.models import SoundFeatures
from app.routers import sounds as sounds_router


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_runtime_state():
    get_settings.cache_clear()
    sounds_router._clear_waveform_cache()
    yield
    sounds_router._clear_waveform_cache()
    get_settings.cache_clear()


def _set_sample_roots(monkeypatch, sample_roots: list[str]) -> None:
    monkeypatch.setenv("SYNTHBUD_SAMPLE_LOCAL_ROOTS", json.dumps(sample_roots))
    get_settings.cache_clear()


def _override_db(sound):
    from app import db as db_module
    session_state = SimpleNamespace(commit_count=0, added=[])

    def dummy_get_db():
        class DummySession:
            def get(self, model, sound_id):
                return sound

            def add(self, obj):
                session_state.added.append(obj)

            def commit(self):
                session_state.commit_count += 1

            def close(self):
                pass

        yield DummySession()

    return db_module.get_db, dummy_get_db, session_state


def _require_persisted_waveform_storage() -> None:
    required = ("waveform_peaks", "waveform_bins")
    missing = [name for name in required if not hasattr(SoundFeatures, name)]
    if missing:
        pytest.xfail(
            "Persistent waveform storage is not implemented on SoundFeatures yet."
        )


def test_sound_waveform_returns_local_file_peaks(tmp_path: Path, monkeypatch):
    sample_root = tmp_path / "samples"
    sample_root.mkdir()
    sample_file = sample_root / "kick.wav"
    sample_file.write_bytes(b"stub")
    _set_sample_roots(monkeypatch, [str(sample_root)])

    sound = SimpleNamespace(
        id=1,
        source="local-filesystem",
        source_sound_id="local-file:test",
        file_url=str(sample_file.resolve()),
        preview_url=None,
        duration_sec=1.25,
    )

    monkeypatch.setattr(
        sounds_router,
        "load_audio_file_to_array",
        lambda path, target_sr: np.array([0.0, 1.0, -2.0, 0.5], dtype=np.float32),
    )
    monkeypatch.setattr(
        sounds_router,
        "compute_waveform_peaks",
        lambda audio, bins: [0.5, 1.0],
    )

    dependency, override, session_state = _override_db(sound)
    app.dependency_overrides[dependency] = override
    try:
        response = client.get("/api/sounds/1/waveform?bins=2")
    finally:
        app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 200
    assert response.json() == {
        "sound_id": 1,
        "bins": 2,
        "duration_sec": 1.25,
        "peaks": [0.5, 1.0],
    }
    assert sound.features.waveform_peaks == [0.5, 1.0]
    assert sound.features.waveform_bins == 72
    assert sound.features.waveform_source_key == build_local_waveform_source_key(sample_file)
    assert session_state.commit_count == 1


def test_sound_waveform_returns_preview_url_peaks(monkeypatch):
    sound = SimpleNamespace(
        id=7,
        source="freesound",
        source_sound_id="7",
        file_url=None,
        preview_url="https://cdn.example.com/previews/7.mp3",
        duration_sec=None,
    )

    monkeypatch.setattr(
        sounds_router,
        "get_settings",
        lambda: SimpleNamespace(feature_sample_rate=4),
    )
    monkeypatch.setattr(
        sounds_router,
        "load_audio_url_to_array",
        lambda url, target_sr: np.array([0.25, -0.25, 0.5, -1.0], dtype=np.float32),
    )
    monkeypatch.setattr(
        sounds_router,
        "compute_waveform_peaks",
        lambda audio, bins: [0.25, 0.25, 0.5, 1.0],
    )

    dependency, override, session_state = _override_db(sound)
    app.dependency_overrides[dependency] = override
    try:
        response = client.get("/api/sounds/7/waveform?bins=4")
    finally:
        app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["sound_id"] == 7
    assert payload["bins"] == 4
    assert payload["duration_sec"] == pytest.approx(1.0)
    assert payload["peaks"] == [0.25, 0.25, 0.5, 1.0]
    assert sound.features.waveform_peaks == [0.25, 0.25, 0.5, 1.0]
    assert sound.features.waveform_bins == 72
    assert sound.features.waveform_source_key == build_remote_waveform_source_key(sound.preview_url)
    assert session_state.commit_count == 1


def test_sound_waveform_reuses_persisted_feature_cache(tmp_path: Path, monkeypatch):
    _require_persisted_waveform_storage()

    sample_root = tmp_path / "samples"
    sample_root.mkdir()
    sample_file = sample_root / "kick.wav"
    sample_file.write_bytes(b"stub")

    features = SoundFeatures(sound_id=1)
    features.waveform_bins = 3
    features.waveform_peaks = [0.2, 0.8, 0.4]
    features.waveform_source_key = build_local_waveform_source_key(sample_file)
    sound = SimpleNamespace(
        id=1,
        source="local-filesystem",
        source_sound_id="local-file:test",
        file_url=str(sample_file.resolve()),
        preview_url=None,
        duration_sec=1.25,
        features=features,
    )

    monkeypatch.setattr(
        sounds_router,
        "get_settings",
        lambda: SimpleNamespace(
            feature_sample_rate=4,
            waveform_default_bins=72,
            sample_local_roots=[str(sample_root)],
        ),
    )

    def _unexpected_audio_decode(*_args, **_kwargs):
        raise AssertionError("waveform audio should not be decoded when cached peaks exist")

    monkeypatch.setattr(sounds_router, "load_audio_file_to_array", _unexpected_audio_decode)
    monkeypatch.setattr(sounds_router, "load_audio_url_to_array", _unexpected_audio_decode)

    dependency, override, session_state = _override_db(sound)
    app.dependency_overrides[dependency] = override
    try:
        response = client.get("/api/sounds/1/waveform?bins=3")
    finally:
        app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 200
    assert response.json() == {
        "sound_id": 1,
        "bins": 3,
        "duration_sec": 1.25,
        "peaks": [0.2, 0.8, 0.4],
    }
    assert session_state.commit_count == 0


def test_sound_waveform_returns_404_when_sound_is_missing():
    dependency, override, _session_state = _override_db(None)
    app.dependency_overrides[dependency] = override
    try:
        response = client.get("/api/sounds/999/waveform")
    finally:
        app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 404
    assert response.json()["detail"] == "Sound not found"


def test_sound_waveform_returns_404_when_no_waveform_source_exists():
    sound = SimpleNamespace(
        id=9,
        source="manual-import",
        source_sound_id="manual-9",
        file_url=None,
        preview_url=None,
        duration_sec=None,
    )

    dependency, override, _session_state = _override_db(sound)
    app.dependency_overrides[dependency] = override
    try:
        response = client.get("/api/sounds/9/waveform")
    finally:
        app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 404
    assert response.json()["detail"] == "No preview available for waveform extraction"
