from collections import Counter
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Preset, Sound


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


@router.get("/synths", response_model=List[str])
def list_synths(db: Session = Depends(get_db)) -> List[str]:
    rows = db.execute(
        select(Preset.synth_name)
        .where(Preset.synth_name.isnot(None))
        .distinct()
        .order_by(Preset.synth_name.asc())
    ).all()
    return [name for (name,) in rows if name]


@router.get("/preset-tags", response_model=List[str])
def list_preset_tags(limit: int = 50, db: Session = Depends(get_db)) -> List[str]:
    rows = db.execute(select(Preset.tags).where(Preset.tags.isnot(None))).all()
    counter: Counter[str] = Counter()
    for (tags,) in rows:
        if not tags:
            continue
        counter.update([tag for tag in tags if tag])
    return [tag for tag, _ in counter.most_common(limit)]

