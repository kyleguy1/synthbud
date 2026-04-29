from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db


router = APIRouter(prefix="/api/health", tags=["health"])
BACKEND_ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def _get_expected_db_revision() -> str | None:
    config_path = BACKEND_ROOT / "alembic.ini"
    script_path = BACKEND_ROOT / "alembic"
    if not config_path.exists() or not script_path.exists():
        return None

    config = Config(str(config_path))
    config.set_main_option("script_location", str(script_path))
    return ScriptDirectory.from_config(config).get_current_head()


@router.get("/", summary="Health check")
def health_check(db: Session = Depends(get_db)) -> dict:
    """
    Simple health endpoint.

    Verifies DB connectivity and returns basic app metadata.
    """
    # Lightweight DB check: run a trivial statement
    db.execute(text("SELECT 1"))

    # Validate that the backend is pointed at the expected application schema,
    # not just any reachable Postgres database.
    required_tables = ("sounds", "sound_features")
    missing_tables = []
    for table_name in required_tables:
        qualified_name = f"public.{table_name}"
        result = db.execute(
            text("SELECT to_regclass(:table_name)"),
            {"table_name": qualified_name},
        )
        if result.scalar_one_or_none() is None:
            missing_tables.append(table_name)

    if missing_tables:
        raise HTTPException(
            status_code=503,
            detail=(
                "Database is reachable but missing required tables: "
                + ", ".join(missing_tables)
                + ". Check SYNTHBUD_DATABASE_URL and run migrations against the intended database."
            ),
        )

    expected_revision = _get_expected_db_revision()
    if expected_revision:
        result = db.execute(
            text("SELECT to_regclass(:table_name)"),
            {"table_name": "public.alembic_version"},
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Database is reachable but missing migration metadata. "
                    f"Run migrations to revision {expected_revision}."
                ),
            )

        current_revision = db.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one_or_none()
        if current_revision != expected_revision:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Database schema is out of date: "
                    f"current revision {current_revision or 'unknown'}, "
                    f"expected {expected_revision}. "
                    "Run migrations and retry."
                ),
            )

    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }
