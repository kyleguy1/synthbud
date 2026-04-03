from typing import List, Optional, Sequence, Tuple

from sqlalchemy import Float, String, and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import Sound, SoundFeatures


def build_sound_search_query(
    db: Session,
    *,
    q: Optional[str] = None,
    tags: Optional[List[str]] = None,
    license_labels: Optional[List[str]] = None,
    min_duration: Optional[float] = None,
    max_duration: Optional[float] = None,
    min_brightness: Optional[float] = None,
    max_brightness: Optional[float] = None,
    bpm_min: Optional[float] = None,
    bpm_max: Optional[float] = None,
    key: Optional[str] = None,
    is_loop: Optional[bool] = None,
) -> Tuple[Sequence[Sound], int]:
    """
    Build and execute a filtered sound search query.
    """
    stmt = (
        select(Sound, SoundFeatures)
        .outerjoin(SoundFeatures, Sound.id == SoundFeatures.sound_id)
    )

    conditions = []

    if q:
        pattern = f"%{q.lower()}%"
        conditions.append(
            or_(
                func.lower(Sound.name).like(pattern),
                func.lower(func.coalesce(Sound.author, "")).like(pattern),
                func.lower(func.coalesce(Sound.description, "")).like(pattern),
                func.array_to_string(
                    func.coalesce(Sound.tags, []), " ", type_=String
                ).ilike(pattern),
            )
        )

    if tags:
        tag_conditions = [
            func.lower(tag) == func.any_(func.lower(Sound.tags))  # type: ignore[arg-type]
            for tag in tags
        ]
        conditions.append(or_(*tag_conditions))

    if license_labels:
        conditions.append(Sound.license_label.in_(license_labels))

    if min_duration is not None:
        conditions.append(Sound.duration_sec >= min_duration)
    if max_duration is not None:
        conditions.append(Sound.duration_sec <= max_duration)

    if min_brightness is not None:
        conditions.append(SoundFeatures.spectral_centroid >= min_brightness)
    if max_brightness is not None:
        conditions.append(SoundFeatures.spectral_centroid <= max_brightness)

    if bpm_min is not None:
        conditions.append(SoundFeatures.bpm >= bpm_min)
    if bpm_max is not None:
        conditions.append(SoundFeatures.bpm <= bpm_max)

    if key:
        conditions.append(func.lower(SoundFeatures.key) == key.lower())

    if is_loop is not None:
        conditions.append(SoundFeatures.is_loop.is_(is_loop))

    if conditions:
        stmt = stmt.where(and_(*conditions))

    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()

    return stmt, total
