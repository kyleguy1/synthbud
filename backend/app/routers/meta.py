from collections import Counter
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Sound


router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/tags", response_model=List[str])
def list_tags(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> List[str]:
    """
    Return the most frequent tags across all sounds.
    """
    rows = db.execute(select(Sound.tags).where(Sound.tags.isnot(None))).all()
    counter: Counter[str] = Counter()
    for (tags,) in rows:
        if not tags:
            continue
        counter.update([t for t in tags if t])
    return [tag for tag, _ in counter.most_common(limit)]


@router.get("/licenses")
def list_licenses() -> dict:
    """
    Return allowed license labels and URLs from configuration.
    """
    settings = get_settings()
    labels = {}
    for url in settings.license_allowlist_urls:
        label = settings.license_label_map.get(str(url), "UNKNOWN")
        labels[label] = str(url)
    return {"licenses": labels}

