from datetime import UTC, datetime

import httpx
from sqlalchemy import or_, select

from app.db import SessionLocal
from app.models import Sound
from app.ingestion.freesound_client import FreesoundClient
from app.ingestion.freesound_ingestor import (
    extract_author,
    extract_preview_url,
    normalize_freesound_source_page_url,
)


def backfill_missing_previews(limit: int | None = None) -> int:
    client = FreesoundClient.from_settings()
    updated_count = 0

    db = SessionLocal()
    try:
        stmt = (
            select(Sound)
            .where(Sound.source == "freesound", Sound.preview_url.is_(None))
            .order_by(Sound.id.asc())
        )
        if limit is not None and limit > 0:
            stmt = stmt.limit(limit)

        sounds = db.execute(stmt).scalars().all()
        for sound in sounds:
            try:
                payload = client.get_sound(
                    int(sound.source_sound_id),
                    fields=["id", "previews", "download", "url", "username"],
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    raise RuntimeError(
                        "Freesound API token is invalid or missing. Set SYNTHBUD_FREESOUND_API_TOKEN in backend/.env."
                    ) from exc
                raise
            except httpx.HTTPError:
                continue

            preview_url = extract_preview_url(payload)
            if not preview_url:
                continue

            sound.author = extract_author(payload) or sound.author
            sound.preview_url = preview_url
            sound.file_url = payload.get("download") or sound.file_url
            sound.source_page_url = normalize_freesound_source_page_url(
                payload.get("url") or sound.source_page_url,
                sound_id=sound.source_sound_id,
                author=sound.author,
            )
            sound.updated_at = datetime.now(UTC)
            updated_count += 1

        db.commit()
        return updated_count
    finally:
        db.close()


def backfill_freesound_source_page_urls(limit: int | None = None) -> int:
    updated_count = 0
    db = SessionLocal()
    try:
        stmt = (
            select(Sound)
            .where(
                Sound.source == "freesound",
                or_(
                    Sound.source_page_url.is_(None),
                    Sound.source_page_url.like("/apiv2/%"),
                    Sound.source_page_url.like("https://freesound.org/apiv2/%"),
                    Sound.source_page_url.like("http://freesound.org/apiv2/%"),
                ),
            )
            .order_by(Sound.id.asc())
        )
        if limit is not None and limit > 0:
            stmt = stmt.limit(limit)

        sounds = db.execute(stmt).scalars().all()
        for sound in sounds:
            normalized_url = normalize_freesound_source_page_url(
                sound.source_page_url,
                sound_id=sound.source_sound_id,
                author=sound.author,
            )
            if not normalized_url or normalized_url == sound.source_page_url:
                continue

            sound.source_page_url = normalized_url
            sound.updated_at = datetime.now(UTC)
            updated_count += 1

        db.commit()
        return updated_count
    finally:
        db.close()


if __name__ == "__main__":
    preview_updates = backfill_missing_previews()
    source_url_updates = backfill_freesound_source_page_urls()
    print(f"Updated preview URLs for {preview_updates} sounds")
    print(f"Updated source URLs for {source_url_updates} sounds")
