from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Sound
from app.ingestion.freesound_client import FreesoundClient
from app.ingestion.freesound_ingestor import extract_author, extract_preview_url


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

            preview_url = extract_preview_url(payload)
            if not preview_url:
                continue

            sound.preview_url = preview_url
            sound.file_url = payload.get("download") or sound.file_url
            sound.source_page_url = payload.get("url") or sound.source_page_url
            sound.author = extract_author(payload) or sound.author
            sound.updated_at = datetime.now(UTC)
            updated_count += 1

        db.commit()
        return updated_count
    finally:
        db.close()


if __name__ == "__main__":
    updated = backfill_missing_previews()
    print(f"Updated preview URLs for {updated} sounds")
