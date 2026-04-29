from __future__ import annotations

import argparse
import atexit
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import shutil
import signal
import subprocess
import sys
from typing import Any, Optional

from dotenv import dotenv_values


DEFAULT_DESKTOP_API_HOST = "127.0.0.1"
DEFAULT_DESKTOP_API_PORT = 38080
DEFAULT_DESKTOP_DB_HOST = "127.0.0.1"
DEFAULT_DESKTOP_DB_PORT = 35432
DEFAULT_DESKTOP_DB_NAME = "synthbud"
DEFAULT_DESKTOP_DB_USER = "postgres"
DEFAULT_DESKTOP_DB_PASSWORD = "postgres"
DESKTOP_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "tauri://localhost",
    "https://tauri.localhost",
]


class DesktopBootstrapError(RuntimeError):
    """Raised when the desktop runtime cannot be initialized."""


@dataclass(frozen=True)
class DesktopPaths:
    app_data_dir: Path
    logs_dir: Path
    exports_dir: Path
    sample_local_dir: Path
    preset_local_dir: Path
    preset_public_metadata_dir: Path
    postgres_data_dir: Path
    postgres_socket_dir: Path
    postgres_log_path: Path
    config_path: Path


@dataclass
class ManagedPostgres:
    pg_ctl_path: Path
    data_dir: Path

    def stop(self) -> None:
        subprocess.run(
            [
                str(self.pg_ctl_path),
                "stop",
                "-D",
                str(self.data_dir),
                "-m",
                "fast",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


_managed_postgres: Optional[ManagedPostgres] = None


def default_app_data_dir() -> Path:
    explicit = os.getenv("SYNTHBUD_DESKTOP_APP_DATA_DIR")
    if explicit:
        return Path(explicit).expanduser().resolve()

    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "synthbud"
    if sys.platform == "win32":
        app_data = Path(os.getenv("APPDATA", home / "AppData" / "Roaming"))
        return app_data / "synthbud"
    return home / ".local" / "share" / "synthbud"


def build_desktop_paths(app_data_dir: Path) -> DesktopPaths:
    return DesktopPaths(
        app_data_dir=app_data_dir,
        logs_dir=app_data_dir / "logs",
        exports_dir=app_data_dir / "exports",
        sample_local_dir=app_data_dir / "samples" / "local",
        preset_local_dir=app_data_dir / "presets" / "local",
        preset_public_metadata_dir=app_data_dir / "presets" / "public" / "metadata",
        postgres_data_dir=app_data_dir / "postgres" / "data",
        postgres_socket_dir=app_data_dir / "postgres" / "socket",
        postgres_log_path=app_data_dir / "logs" / "postgres.log",
        config_path=app_data_dir / "desktop-config.json",
    )


def ensure_desktop_directories(paths: DesktopPaths) -> None:
    for directory in (
        paths.app_data_dir,
        paths.logs_dir,
        paths.exports_dir,
        paths.sample_local_dir,
        paths.preset_local_dir,
        paths.preset_public_metadata_dir,
        paths.postgres_data_dir.parent,
        paths.postgres_socket_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def default_desktop_config(
    paths: DesktopPaths,
    *,
    api_host: str = DEFAULT_DESKTOP_API_HOST,
    api_port: int = DEFAULT_DESKTOP_API_PORT,
    db_port: int = DEFAULT_DESKTOP_DB_PORT,
) -> dict[str, Any]:
    return {
        "version": 1,
        "api": {
            "host": api_host,
            "port": api_port,
        },
        "postgres": {
            "host": DEFAULT_DESKTOP_DB_HOST,
            "port": db_port,
            "database": DEFAULT_DESKTOP_DB_NAME,
            "user": DEFAULT_DESKTOP_DB_USER,
            "password": DEFAULT_DESKTOP_DB_PASSWORD,
            "bin_dir": os.getenv("SYNTHBUD_DESKTOP_POSTGRES_BIN_DIR"),
            "data_dir": str(paths.postgres_data_dir),
            "socket_dir": str(paths.postgres_socket_dir),
            "log_path": str(paths.postgres_log_path),
        },
        "paths": {
            "app_data_dir": str(paths.app_data_dir),
            "logs_dir": str(paths.logs_dir),
            "exports_dir": str(paths.exports_dir),
            "sample_local_roots": [str(paths.sample_local_dir)],
            "preset_local_roots": [str(paths.preset_local_dir)],
            "preset_public_metadata_roots": [str(paths.preset_public_metadata_dir)],
        },
    }


def load_or_create_desktop_config(
    paths: DesktopPaths,
    *,
    api_host: str = DEFAULT_DESKTOP_API_HOST,
    api_port: int = DEFAULT_DESKTOP_API_PORT,
    db_port: int = DEFAULT_DESKTOP_DB_PORT,
) -> dict[str, Any]:
    ensure_desktop_directories(paths)
    defaults = default_desktop_config(paths, api_host=api_host, api_port=api_port, db_port=db_port)
    if paths.config_path.exists():
        config = json.loads(paths.config_path.read_text(encoding="utf-8"))
        config.setdefault("api", {}).setdefault("host", defaults["api"]["host"])
        config["api"].setdefault("port", defaults["api"]["port"])
        config.setdefault("postgres", {})
        for key, value in defaults["postgres"].items():
            config["postgres"].setdefault(key, value)
        config.setdefault("paths", {})
        for key, value in defaults["paths"].items():
            config["paths"].setdefault(key, value)
        if config != json.loads(paths.config_path.read_text(encoding="utf-8")):
            paths.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return config

    config = defaults
    paths.config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config


def resolve_backend_roots() -> tuple[Path, Path]:
    explicit_root = os.getenv("SYNTHBUD_DESKTOP_BACKEND_ROOT")
    if explicit_root:
        backend_root = Path(explicit_root).expanduser().resolve()
        repo_root = backend_root.parent if backend_root.name == "backend" else backend_root
        return repo_root, backend_root

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        # Inside a PyInstaller-frozen binary, alembic.ini and the alembic/
        # tree are unpacked into _MEIPASS at the bundle root. Treat that
        # directory as both the backend and repo root so run_migrations
        # can locate them without referencing the dev source tree.
        bundled_root = Path(meipass).resolve()
        return bundled_root, bundled_root

    backend_root = Path(__file__).resolve().parents[1]
    repo_root = backend_root.parent
    return repo_root, backend_root


def read_backend_env_value(name: str, backend_root: Optional[Path] = None) -> Optional[str]:
    resolved_backend_root = backend_root or resolve_backend_roots()[1]
    env_path = resolved_backend_root / ".env"
    if not env_path.exists():
        return None

    value = dotenv_values(env_path).get(name)
    if not isinstance(value, str):
        return None

    stripped = value.strip()
    return stripped or None


def resolve_postgres_binary(name: str, configured_bin_dir: Optional[str]) -> Optional[Path]:
    candidates = []
    if configured_bin_dir:
        candidates.append(Path(configured_bin_dir) / name)
    env_bin_dir = os.getenv("SYNTHBUD_DESKTOP_POSTGRES_BIN_DIR")
    if env_bin_dir:
        candidates.append(Path(env_bin_dir) / name)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    on_path = shutil.which(name)
    return Path(on_path) if on_path else None


def build_database_url(config: dict[str, Any]) -> str:
    postgres_config = config["postgres"]
    return (
        "postgresql+psycopg2://"
        f"{postgres_config['user']}:{postgres_config['password']}"
        f"@{postgres_config['host']}:{postgres_config['port']}/{postgres_config['database']}"
    )


def ensure_database_exists(config: dict[str, Any]) -> None:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    postgres_config = config["postgres"]
    connection = psycopg2.connect(
        dbname="postgres",
        user=postgres_config["user"],
        password=postgres_config["password"],
        host=postgres_config["host"],
        port=postgres_config["port"],
    )
    try:
        connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (postgres_config["database"],))
            exists = cursor.fetchone() is not None
            if not exists:
                cursor.execute(f'CREATE DATABASE "{postgres_config["database"]}"')
    finally:
        connection.close()


def _postgres_server_major_version(initdb_path: Path) -> Optional[str]:
    try:
        completed = subprocess.run(
            [str(initdb_path), "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.SubprocessError:
        return None

    # `initdb (PostgreSQL) 16.13 (Homebrew)` -> "16"
    parts = completed.stdout.strip().split()
    for token in parts:
        if "." in token and token.split(".")[0].isdigit():
            return token.split(".")[0]
    return None


def initialize_postgres_cluster(initdb_path: Path, paths: DesktopPaths, config: dict[str, Any]) -> None:
    pg_version_path = paths.postgres_data_dir / "PG_VERSION"
    if pg_version_path.exists():
        existing_major = pg_version_path.read_text(encoding="utf-8").strip()
        bundled_major = _postgres_server_major_version(initdb_path)
        if bundled_major and existing_major == bundled_major:
            return

        # The bundled Postgres can't open a cluster from a different major
        # version (this happens after upgrading the app or migrating from a
        # dev-era Docker Postgres). Rename the stale dir aside and re-init
        # rather than crashing on every launch. The old dir is preserved so
        # the user can recover it manually if they had data there.
        archive_target = paths.postgres_data_dir.with_name(
            f"data.stale-pg{existing_major or 'unknown'}-{int(datetime.now(UTC).timestamp())}"
        )
        os.rename(paths.postgres_data_dir, archive_target)
        paths.postgres_data_dir.mkdir(parents=True, exist_ok=True)

    # Force a deterministic locale. When the desktop app is launched from
    # Finder/launchd there is no inherited LANG/LC_* and initdb refuses to
    # guess. C locale + UTF-8 encoding works on every macOS install and
    # matches what the existing Docker-Postgres dev setup uses.
    initdb_env = os.environ.copy()
    initdb_env.setdefault("LC_ALL", "C")
    initdb_env.setdefault("LANG", "C")

    subprocess.run(
        [
            str(initdb_path),
            "-D",
            str(paths.postgres_data_dir),
            "-U",
            config["postgres"]["user"],
            "-A",
            "trust",
            "--locale=C",
            "--encoding=UTF8",
        ],
        check=True,
        env=initdb_env,
    )


def build_postgres_start_options(config: dict[str, Any]) -> str:
    # The desktop runtime connects over TCP, so we don't need a Unix socket dir here.
    # Avoiding `-k <path>` also keeps macOS "Application Support" paths from breaking
    # the server startup when Postgres parses the options string.
    return f"-p {config['postgres']['port']} -h {config['postgres']['host']}"


def start_managed_postgres(paths: DesktopPaths, config: dict[str, Any]) -> Optional[ManagedPostgres]:
    initdb_path = resolve_postgres_binary("initdb", config["postgres"].get("bin_dir"))
    pg_ctl_path = resolve_postgres_binary("pg_ctl", config["postgres"].get("bin_dir"))
    if not initdb_path or not pg_ctl_path:
        return None

    initialize_postgres_cluster(initdb_path, paths, config)

    # macOS-specific: Postgres aborts with "postmaster became multithreaded
    # during startup" if its locale resolution triggers Apple's threaded
    # locale helpers. Forcing a concrete BSD-recognised locale before
    # pg_ctl runs avoids that path. en_US.UTF-8 ships on every macOS.
    pg_env = os.environ.copy()
    pg_env["LC_ALL"] = "en_US.UTF-8"
    pg_env["LANG"] = "en_US.UTF-8"

    subprocess.run(
        [
            str(pg_ctl_path),
            "start",
            "-D",
            str(paths.postgres_data_dir),
            "-l",
            str(paths.postgres_log_path),
            "-o",
            build_postgres_start_options(config),
            "-w",
        ],
        check=True,
        env=pg_env,
    )
    ensure_database_exists(config)
    return ManagedPostgres(pg_ctl_path=pg_ctl_path, data_dir=paths.postgres_data_dir)


def apply_desktop_environment(paths: DesktopPaths, config: dict[str, Any], database_url: str) -> None:
    os.environ["SYNTHBUD_DESKTOP_MODE"] = "true"
    os.environ["SYNTHBUD_DESKTOP_APP_DATA_DIR"] = str(paths.app_data_dir)
    os.environ["SYNTHBUD_DESKTOP_CONFIG_PATH"] = str(paths.config_path)
    os.environ["SYNTHBUD_DESKTOP_EXPORTS_DIR"] = str(paths.exports_dir)
    os.environ["SYNTHBUD_DESKTOP_LOGS_DIR"] = str(paths.logs_dir)
    os.environ["SYNTHBUD_DATABASE_URL"] = database_url
    os.environ["SYNTHBUD_SAMPLE_LOCAL_ROOTS"] = json.dumps(config["paths"]["sample_local_roots"])
    os.environ["SYNTHBUD_PRESET_LOCAL_ROOTS"] = json.dumps(config["paths"]["preset_local_roots"])
    os.environ["SYNTHBUD_PRESET_PUBLIC_METADATA_ROOTS"] = json.dumps(
        config["paths"]["preset_public_metadata_roots"]
    )
    os.environ["SYNTHBUD_CORS_ALLOW_ORIGINS"] = json.dumps(DESKTOP_ALLOWED_ORIGINS)


def _resolve_alembic_ini(repo_root: Path) -> Path:
    # In a frozen PyInstaller bundle resolve_backend_roots() returns _MEIPASS
    # for both repo_root and backend_root, and alembic.ini is unpacked at the
    # bundle root rather than under backend/.
    if getattr(sys, "frozen", False):
        bundled_ini = repo_root / "alembic.ini"
        if bundled_ini.exists():
            return bundled_ini
    return repo_root / "backend" / "alembic.ini"


def run_migrations(repo_root: Path) -> None:
    alembic_ini = _resolve_alembic_ini(repo_root)

    if getattr(sys, "frozen", False):
        # `sys.executable` is the frozen synthbud-backend binary, so spawning
        # `-m alembic` would re-enter the launcher. Run alembic in-process and
        # override `script_location` because the bundled layout flattens
        # `backend/alembic` to `<bundle>/alembic`.
        #
        # alembic loads env.py via importlib.exec_module in a fresh module
        # context. PyInstaller's embedded importer is already installed at
        # this point, but the symbolic top-level packages env.py imports
        # (`app.config`, `app.db`, `app.models`) only get registered in
        # sys.modules once *something* imports them. Pre-importing them here
        # keeps env.py's `from app.config import ...` from raising
        # ModuleNotFoundError.
        import app  # noqa: F401
        import app.config  # noqa: F401
        import app.db  # noqa: F401
        import app.models  # noqa: F401

        from alembic import command as alembic_command
        from alembic.config import Config as AlembicConfig

        alembic_cfg = AlembicConfig(str(alembic_ini))
        alembic_cfg.set_main_option("script_location", str(repo_root / "alembic"))
        alembic_command.upgrade(alembic_cfg, "head")
        return

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "backend")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(alembic_ini),
            "upgrade",
            "head",
        ],
        cwd=str(repo_root),
        env=env,
        check=True,
    )


def prepare_desktop_runtime(
    *,
    app_data_dir: Optional[Path] = None,
    api_host: str = DEFAULT_DESKTOP_API_HOST,
    api_port: int = DEFAULT_DESKTOP_API_PORT,
    db_port: int = DEFAULT_DESKTOP_DB_PORT,
) -> tuple[DesktopPaths, dict[str, Any], Optional[ManagedPostgres]]:
    global _managed_postgres

    paths = build_desktop_paths((app_data_dir or default_app_data_dir()).resolve())
    config = load_or_create_desktop_config(paths, api_host=api_host, api_port=api_port, db_port=db_port)
    repo_root, backend_root = resolve_backend_roots()

    explicit_database_url = os.getenv("SYNTHBUD_DATABASE_URL")
    database_url_from_backend_env = read_backend_env_value("SYNTHBUD_DATABASE_URL", backend_root)
    managed_postgres = None
    if explicit_database_url:
        database_url = explicit_database_url
    elif database_url_from_backend_env:
        database_url = database_url_from_backend_env
    else:
        managed_postgres = start_managed_postgres(paths, config)
        database_url = build_database_url(config) if managed_postgres else (
            "postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/synthbud"
        )

    apply_desktop_environment(paths, config, database_url)
    run_migrations(repo_root)
    _managed_postgres = managed_postgres
    return paths, config, managed_postgres


def shutdown_desktop_runtime() -> None:
    global _managed_postgres
    if _managed_postgres:
        _managed_postgres.stop()
        _managed_postgres = None


def _handle_exit_signal(_signum, _frame) -> None:
    shutdown_desktop_runtime()
    raise SystemExit(0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Desktop launcher for the synthbud backend.")
    parser.add_argument("--host", default=os.getenv("SYNTHBUD_DESKTOP_API_HOST", DEFAULT_DESKTOP_API_HOST))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("SYNTHBUD_DESKTOP_API_PORT", str(DEFAULT_DESKTOP_API_PORT))),
    )
    parser.add_argument(
        "--db-port",
        type=int,
        default=int(os.getenv("SYNTHBUD_DESKTOP_DB_PORT", str(DEFAULT_DESKTOP_DB_PORT))),
    )
    parser.add_argument(
        "--app-data-dir",
        default=os.getenv("SYNTHBUD_DESKTOP_APP_DATA_DIR"),
        help="Override the desktop app data directory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    atexit.register(shutdown_desktop_runtime)
    signal.signal(signal.SIGINT, _handle_exit_signal)
    signal.signal(signal.SIGTERM, _handle_exit_signal)

    app_data_dir = Path(args.app_data_dir).expanduser() if args.app_data_dir else None
    prepare_desktop_runtime(
        app_data_dir=app_data_dir,
        api_host=args.host,
        api_port=args.port,
        db_port=args.db_port,
    )

    import uvicorn

    # Import the FastAPI instance directly rather than passing the
    # "app.main:app" import string. uvicorn's string form spawns a fresh
    # importer context that PyInstaller's embedded loader can't satisfy
    # ("Could not import module 'app.main'"); handing it a live ASGI
    # callable bypasses that path entirely.
    from app.main import app as fastapi_app

    uvicorn.run(
        fastapi_app,
        host=args.host,
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
