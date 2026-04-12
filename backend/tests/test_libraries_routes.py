import json
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set_env(monkeypatch, *, sample_roots: list[str], preset_roots: list[str], config_path: Path | None = None) -> None:
    monkeypatch.setenv("SYNTHBUD_SAMPLE_LOCAL_ROOTS", json.dumps(sample_roots))
    monkeypatch.setenv("SYNTHBUD_PRESET_LOCAL_ROOTS", json.dumps(preset_roots))
    monkeypatch.setenv("SYNTHBUD_DESKTOP_MODE", "true")
    if config_path is not None:
        monkeypatch.setenv("SYNTHBUD_DESKTOP_CONFIG_PATH", str(config_path))
    else:
        monkeypatch.delenv("SYNTHBUD_DESKTOP_CONFIG_PATH", raising=False)
    get_settings.cache_clear()


def test_list_libraries_returns_current_runtime_roots(tmp_path: Path, monkeypatch):
    sample_root = tmp_path / "samples"
    preset_root = tmp_path / "presets"
    sample_root.mkdir()
    preset_root.mkdir()

    _set_env(monkeypatch, sample_roots=[str(sample_root)], preset_roots=[str(preset_root)])

    response = client.get("/api/libraries/")

    assert response.status_code == 200
    assert response.json() == {
        "desktop_mode": True,
        "sample_roots": [str(sample_root.resolve())],
        "preset_roots": [str(preset_root.resolve())],
    }


def test_import_sample_library_updates_roots_and_runs_ingestion(tmp_path: Path, monkeypatch):
    sample_root = tmp_path / "New Samples"
    sample_root.mkdir(parents=True)
    config_path = tmp_path / "desktop-config.json"
    config_path.write_text(json.dumps({"paths": {"sample_local_roots": [], "preset_local_roots": []}}), encoding="utf-8")
    _set_env(monkeypatch, sample_roots=[], preset_roots=[], config_path=config_path)

    from app.routers import libraries as libraries_router

    monkeypatch.setattr(
        libraries_router,
        "ingest_local_sounds",
        lambda: {"ingested_count": 4, "scanned_files": 7, "failed_count": 1},
    )

    response = client.post("/api/libraries/samples/import", json={"path": str(sample_root)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "samples"
    assert payload["effective_path"] == str(sample_root.resolve())
    assert payload["roots"] == [str(sample_root.resolve())]
    assert payload["import_result"]["ingested_count"] == 4
    updated_config = json.loads(config_path.read_text(encoding="utf-8"))
    assert updated_config["paths"]["sample_local_roots"] == [str(sample_root.resolve())]


def test_import_preset_library_normalizes_bank_folder_to_library_root(tmp_path: Path, monkeypatch):
    bank_folder = tmp_path / "Preset Library" / "serum" / "My Bank"
    bank_folder.mkdir(parents=True)
    config_path = tmp_path / "desktop-config.json"
    config_path.write_text(json.dumps({"paths": {"sample_local_roots": [], "preset_local_roots": []}}), encoding="utf-8")
    _set_env(monkeypatch, sample_roots=[], preset_roots=[], config_path=config_path)

    from app.routers import libraries as libraries_router

    monkeypatch.setattr(
        libraries_router,
        "ingest_local_presets",
        lambda: {"ingested_count": 2, "scanned_files": 2, "parse_failed_count": 0},
    )

    response = client.post("/api/libraries/presets/import", json={"path": str(bank_folder)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "presets"
    assert payload["effective_path"] == str((tmp_path / "Preset Library").resolve())
    assert payload["roots"] == [str((tmp_path / "Preset Library").resolve())]


def test_local_sound_preview_and_download_stream_local_file(tmp_path: Path, monkeypatch):
    sample_root = tmp_path / "samples"
    sample_root.mkdir()
    sample_file = sample_root / "kick.wav"
    with wave.open(str(sample_file), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(22050)
        wav_file.writeframes(b"\x00\x00" * 2205)

    _set_env(monkeypatch, sample_roots=[str(sample_root)], preset_roots=[])

    from app import db as db_module

    sound = SimpleNamespace(
        id=1,
        source="local-filesystem",
        source_sound_id="local-file:test",
        file_url=str(sample_file.resolve()),
    )

    def dummy_get_db():
        class DummySession:
            def get(self, model, sound_id):
                assert sound_id == 1
                return sound

            def close(self):
                pass

        yield DummySession()

    app.dependency_overrides[db_module.get_db] = dummy_get_db
    try:
        preview_response = client.get("/api/sounds/1/preview")
        download_response = client.get("/api/sounds/1/download")
    finally:
        app.dependency_overrides.pop(db_module.get_db, None)

    assert preview_response.status_code == 200
    assert preview_response.content
    assert download_response.status_code == 200
    assert "kick.wav" in download_response.headers.get("content-disposition", "")
