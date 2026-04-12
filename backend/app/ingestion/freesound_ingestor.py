from contextlib import contextmanager
from datetime import UTC, datetime
import re
from typing import Iterable, List
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import IngestionRun, IngestionStatusEnum, Sound
from app.tag_taxonomy import reconcile_tag_fields
from .freesound_client import FreesoundClient


SEARCH_QUERIES: List[str] = [
    "synth",
    "synth pluck",
    "lead",
    "keys",
    "pad",
]

FREESOUND_OWNER_SOUND_RE = re.compile(r"^/people/(?P<owner>[^/]+)/sounds/(?P<sound_id>\d+)/?$")
FREESOUND_API_SOUND_RE = re.compile(r"^/apiv2/sounds/(?P<sound_id>\d+)/?$")


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
    normalized = license_url.replace("http://", "https://", 1)
    allowlist = {str(url).replace("http://", "https://", 1) for url in settings.license_allowlist_urls}
    return normalized in allowlist


def normalize_license_label(license_url: str) -> str | None:
    settings = get_settings()
    normalized = license_url.replace("http://", "https://", 1)
    return settings.license_label_map.get(normalized)


def extract_preview_url(payload: dict) -> str | None:
    previews = payload.get("previews") or {}
    # Freesound preview keys are hyphenated; keep underscore variants for old payloads.
    return (
        previews.get("preview-hq-mp3")
        or previews.get("preview-lq-mp3")
        or previews.get("preview_hq_mp3")
        or previews.get("preview_lq_mp3")
    )


def extract_author(payload: dict) -> str | None:
    # Search API usually exposes "username". Keep nested "user.username" fallback.
    return payload.get("username") or (payload.get("user") or {}).get("username")


def normalize_freesound_source_page_url(
    source_page_url: str | None,
    *,
    sound_id: str | int | None = None,
    author: str | None = None,
) -> str | None:
    if not source_page_url and not sound_id:
        return None

    parsed = urlparse((source_page_url or "").strip())
    path = parsed.path or ""

    if parsed.netloc and "freesound.org" not in parsed.netloc:
        return source_page_url

    owner_match = FREESOUND_OWNER_SOUND_RE.match(path)
    if owner_match:
        owner = owner_match.group("owner")
        normalized_sound_id = owner_match.group("sound_id")
        return f"https://freesound.org/people/{owner}/sounds/{normalized_sound_id}/"

    api_match = FREESOUND_API_SOUND_RE.match(path)
    if api_match:
        normalized_sound_id = api_match.group("sound_id")
        if author:
            return f"https://freesound.org/people/{author}/sounds/{normalized_sound_id}/"
        return f"https://freesound.org/sounds/{normalized_sound_id}/"

    if sound_id and author:
        return f"https://freesound.org/people/{author}/sounds/{sound_id}/"

    if source_page_url:
        return source_page_url

    return None


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

    raw_tags, canonical_tags = reconcile_tag_fields(raw_tags=payload.get("tags") or [])

    sound.name = payload.get("name") or sound.name
    sound.description = payload.get("description") or payload.get("tags", "")
    sound.raw_tags = raw_tags
    sound.tags = canonical_tags
    sound.duration_sec = payload.get("duration")
    sound.sample_rate = payload.get("samplerate")
    sound.channels = payload.get("channels")

    sound.preview_url = extract_preview_url(payload)
    sound.file_url = payload.get("download")
    sound.author = extract_author(payload)
    sound.source_page_url = normalize_freesound_source_page_url(
        payload.get("url"),
        sound_id=source_sound_id,
        author=sound.author,
    )

    license_url = payload.get("license") or ""
    sound.license_url = license_url
    sound.license_label = normalize_license_label(license_url)

    sound.updated_at = datetime.now(UTC)

    return sound


def run_ingestion(max_pages_per_query: int | None = None) -> None:
    client = FreesoundClient.from_settings()
    with db_session() as db:
        run = IngestionRun(source="freesound", started_at=datetime.now(UTC))
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

            run.status = IngestionStatusEnum.SUCCESS
            run.finished_at = datetime.now(UTC)
            run.details = {
                "ingested_count": ingested_count,
                "queries": SEARCH_QUERIES,
            }
        except Exception as exc:  # pragma: no cover - defensive
            run.status = IngestionStatusEnum.ERROR
            run.finished_at = datetime.now(UTC)
            run.details = {
                "error": str(exc),
                "ingested_count": ingested_count,
            }
            raise


if __name__ == "__main__":
    run_ingestion()
