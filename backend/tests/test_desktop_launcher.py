import json
import os
from pathlib import Path

from app import desktop_launcher


def test_build_desktop_paths_creates_expected_structure(tmp_path: Path):
    paths = desktop_launcher.build_desktop_paths(tmp_path)

    assert paths.logs_dir == tmp_path / "logs"
    assert paths.exports_dir == tmp_path / "exports"
    assert paths.sample_local_dir == tmp_path / "samples" / "local"
    assert paths.preset_local_dir == tmp_path / "presets" / "local"
    assert paths.preset_public_metadata_dir == tmp_path / "presets" / "public" / "metadata"
    assert paths.postgres_data_dir == tmp_path / "postgres" / "data"
    assert paths.config_path == tmp_path / "desktop-config.json"


def test_load_or_create_desktop_config_writes_defaults(tmp_path: Path):
    paths = desktop_launcher.build_desktop_paths(tmp_path)

    config = desktop_launcher.load_or_create_desktop_config(paths, api_port=39080, db_port=39432)

    assert paths.config_path.exists()
    assert config["api"]["port"] == 39080
    assert config["postgres"]["port"] == 39432
    assert config["paths"]["sample_local_roots"] == [str(paths.sample_local_dir)]
    assert config["paths"]["preset_local_roots"] == [str(paths.preset_local_dir)]
    assert json.loads(paths.config_path.read_text(encoding="utf-8"))["version"] == 1


def test_apply_desktop_environment_sets_runtime_paths(tmp_path: Path, monkeypatch):
    paths = desktop_launcher.build_desktop_paths(tmp_path)
    config = desktop_launcher.default_desktop_config(paths)

    monkeypatch.delenv("SYNTHBUD_DATABASE_URL", raising=False)
    desktop_launcher.apply_desktop_environment(paths, config, "postgresql+psycopg2://example")

    assert json.loads(os.environ["SYNTHBUD_SAMPLE_LOCAL_ROOTS"]) == [str(paths.sample_local_dir)]
    assert json.loads(os.environ["SYNTHBUD_PRESET_LOCAL_ROOTS"]) == [str(paths.preset_local_dir)]
    assert os.environ["SYNTHBUD_DESKTOP_MODE"] == "true"
    assert os.environ["SYNTHBUD_DATABASE_URL"] == "postgresql+psycopg2://example"


def test_build_postgres_start_options_uses_tcp_only(tmp_path: Path):
    paths = desktop_launcher.build_desktop_paths(tmp_path / "Application Support" / "synthbud")
    config = desktop_launcher.default_desktop_config(paths, db_port=39432)

    options = desktop_launcher.build_postgres_start_options(config)

    assert options == "-p 39432 -h 127.0.0.1"
    assert "-k" not in options


def test_read_backend_env_value_reads_backend_dotenv(tmp_path: Path):
    backend_root = tmp_path / "backend"
    backend_root.mkdir()
    (backend_root / ".env").write_text(
        "SYNTHBUD_DATABASE_URL=postgresql+psycopg2://postgres:postgres@127.0.0.1:5433/synthbud\n",
        encoding="utf-8",
    )

    value = desktop_launcher.read_backend_env_value("SYNTHBUD_DATABASE_URL", backend_root)

    assert value == "postgresql+psycopg2://postgres:postgres@127.0.0.1:5433/synthbud"


def test_prepare_desktop_runtime_uses_backend_dotenv_database_url(tmp_path: Path, monkeypatch):
    backend_root = tmp_path / "backend"
    backend_root.mkdir()
    (backend_root / ".env").write_text(
        "SYNTHBUD_DATABASE_URL=postgresql+psycopg2://postgres:postgres@127.0.0.1:5433/synthbud\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("SYNTHBUD_DESKTOP_BACKEND_ROOT", str(backend_root))
    monkeypatch.delenv("SYNTHBUD_DATABASE_URL", raising=False)

    migrations_called = {"value": False}

    def fake_run_migrations(repo_root: Path) -> None:
        migrations_called["value"] = True
        assert repo_root == tmp_path

    monkeypatch.setattr(desktop_launcher, "run_migrations", fake_run_migrations)
    monkeypatch.setattr(desktop_launcher, "start_managed_postgres", lambda *_args, **_kwargs: None)

    paths, _config, managed_postgres = desktop_launcher.prepare_desktop_runtime(app_data_dir=tmp_path / "app-data")

    assert managed_postgres is None
    assert migrations_called["value"] is True
    assert paths.config_path.exists()
    assert os.environ["SYNTHBUD_DATABASE_URL"] == (
        "postgresql+psycopg2://postgres:postgres@127.0.0.1:5433/synthbud"
    )
