from fastapi import APIRouter, Depends
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

    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
    }
