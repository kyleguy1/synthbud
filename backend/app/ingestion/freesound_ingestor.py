from contextlib import contextmanager
from datetime import datetime
from typing import Iterable, List

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import IngestionRun, Sound
from .freesound_client import FreesoundClient


SEARCH_QUERIES: List[str] = [
    "synth",
    "synth pluck",
    "lead",
    "keys",
    "pad",
]


@contextmanager
def db_session() -> Iterable[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def is_license_allowed(license_url: str) -> bool:
    settings = get_settings()
    return license_url in settings.license_allowlist_urls


def normalize_license_label(license_url: str) -> str | None:
    settings = get_settings()
    return settings.license_label_map.get(license_url)


def upsert_sound_from_payload(db: Session, payload: dict) -> Sound:
    source = "freesound"
    source_sound_id = str(payload["id"])

    sound = (
        db.query(Sound)
        .filter(Sound.source == source, Sound.source_sound_id == source_sound_id)
        .first()
    )

    if sound is None:
        sound = Sound(source=source, source_sound_id=source_sound_id, name=payload.get("name") or "")
        db.add(sound)

    sound.name = payload.get("name") or sound.name
    sound.description = payload.get("description") or payload.get("tags", "")
    sound.tags = payload.get("tags") or []
    sound.duration_sec = payload.get("duration")
    sound.sample_rate = payload.get("samplerate")
    sound.channels = payload.get("channels")

    sound.preview_url = (payload.get("previews") or {}).get("preview_hq_mp3")
    sound.file_url = payload.get("download")
    sound.source_page_url = payload.get("url")

    license_url = payload.get("license") or ""
    sound.license_url = license_url
    sound.license_label = normalize_license_label(license_url)
    username = (payload.get("user") or {}).get("username")
    sound.author = username

    sound.updated_at = datetime.utcnow()

    return sound


def run_ingestion(max_pages_per_query: int | None = None) -> None:
    client = FreesoundClient.from_settings()
    settings = get_settings()

    with db_session() as db:
        run = IngestionRun(source="freesound", started_at=datetime.utcnow())
        db.add(run)
        db.flush()

        ingested_count = 0

        try:
            for query in SEARCH_QUERIES:
                for page_data in client.paged_search(
                    query=query,
                    page_size=50,
                    max_pages=max_pages_per_query,
                    fields=[
                        "id",
                        "name",
                        "description",
                        "tags",
                        "duration",
                        "samplerate",
                        "channels",
                        "license",
                        "username",
                        "url",
                        "download",
                        "previews",
                    ],
                ):
                    for item in page_data.get("results") or []:
                        license_url = item.get("license") or ""
                        if not license_url or not is_license_allowed(license_url):
                            continue

                        sound = upsert_sound_from_payload(db, item)
                        ingested_count += 1

            run.status = "success"
            run.finished_at = datetime.utcnow()
            run.details = {
                "ingested_count": ingested_count,
                "queries": SEARCH_QUERIES,
            }
        except Exception as exc:  # pragma: no cover - defensive
            run.status = "error"
            run.finished_at = datetime.utcnow()
            run.details = {
                "error": str(exc),
                "ingested_count": ingested_count,
            }
            raise


if __name__ == "__main__":
    run_ingestion()

