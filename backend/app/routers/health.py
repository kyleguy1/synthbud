from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db


router = APIRouter(prefix="/api/health", tags=["health"])


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

    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }
