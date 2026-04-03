from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from time import monotonic, sleep
from typing import Any, TypedDict
from urllib.parse import parse_qs, urljoin, urlparse
import logging
import re

import httpx
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)

PRESETSHARE_BASE_URL = "https://presetshare.com"
PRESETSHARE_PRESETS_PATH = "/presets"
PRESETSHARE_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
DEFAULT_CACHE_TTL_SECONDS = 3600
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 1.0

SYNTH_NAME_TO_ID = {
    "serum": 1,
    "vital": 2,
    "massive": 3,
    "fm8": 4,
    "harmor": 5,
    "sytrus": 6,
    "surge": 7,
    "massivex": 8,
    "phase plant": 9,
    "spire": 10,
    "patcher": 11,
    "diva": 12,
    "zebra": 13,
    "sylenth1": 25,
    "helm": 28,
    "pigments": 35,
    "serum 2": 59,
}

GENRE_NAME_TO_ID = {
    "drum and bass": 1,
    "dubstep": 3,
    "house": 4,
    "bass house": 5,
    "future bass": 6,
    "trap": 7,
    "hip-hop / r&b": 8,
    "techno": 9,
    "synthwave": 10,
    "other": 11,
    "trance": 13,
    "multigenre": 14,
    "midtempo": 15,
    "cinematic": 16,
    "uk garage": 17,
    "ambient": 18,
    "psytrance": 21,
}

SOUND_TYPE_NAME_TO_ID = {
    "arp": 1,
    "seq": 2,
    "drums": 3,
    "fx": 4,
    "pluck": 5,
    "keys": 6,
    "bass": 7,
    "reese": 8,
    "stab": 9,
    "chord": 10,
    "lead": 11,
    "pad": 12,
    "drone": 13,
    "atmosphere": 14,
    "vox": 15,
    "synth": 16,
    "sub": 17,
    "miscellaneous": 18,
    "other": 19,
}

SYNTH_ID_TO_NAME = {value: key.title() for key, value in SYNTH_NAME_TO_ID.items()}
SYNTH_ID_TO_NAME[59] = "Serum 2"
GENRE_ID_TO_NAME = {value: key.title() for key, value in GENRE_NAME_TO_ID.items()}
SOUND_TYPE_ID_TO_NAME = {value: key.title() for key, value in SOUND_TYPE_NAME_TO_ID.items()}
SOUND_TYPE_ID_TO_NAME[4] = "FX"


class PresetsharePreset(TypedDict):
    id: str
    name: str
    url: str
    synth: str | None
    synthId: int | None
    genre: str | None
    genreId: int | None
    soundType: str | None
    soundTypeId: int | None
    author: str | None
    authorUrl: str | None
    datePosted: str | None
    likes: int
    downloads: int
    comments: int
    source: str


@dataclass
class _CacheEntry:
    expires_at: datetime
    data: list[PresetsharePreset]


_cache_lock = Lock()
_cache: dict[str, _CacheEntry] = {}
_last_request_ts = 0.0

_PRESET_URL_RE = re.compile(r"/p(?P<id>\d+)")
_INT_RE = re.compile(r"\d+")


def normalize_name_key(value: str | None) -> str:
    return (value or "").strip().lower()


def resolve_synth_id(name: str | None) -> int | None:
    if not name:
        return None
    return SYNTH_NAME_TO_ID.get(normalize_name_key(name))


def resolve_genre_id(name: str | None) -> int | None:
    if not name:
        return None
    return GENRE_NAME_TO_ID.get(normalize_name_key(name))


def resolve_sound_type_id(name: str | None) -> int | None:
    if not name:
        return None
    return SOUND_TYPE_NAME_TO_ID.get(normalize_name_key(name))


def list_supported_synth_names() -> list[str]:
    return sorted(SYNTH_ID_TO_NAME.values())


def list_supported_genre_names() -> list[str]:
    return sorted(GENRE_ID_TO_NAME.values())


def list_supported_sound_type_names() -> list[str]:
    return sorted(SOUND_TYPE_ID_TO_NAME.values())


def build_cache_key(
    *,
    instrument: int | None,
    genre: int | None,
    sound_type: int | None,
    page: int,
) -> str:
    return f"presets:{instrument}:{genre}:{sound_type}:{page}"


def clear_cache(key: str | None = None) -> int:
    with _cache_lock:
        if key is not None:
            return 1 if _cache.pop(key, None) is not None else 0
        removed = len(_cache)
        _cache.clear()
        return removed


def _safe_int(text: str | None) -> int:
    if not text:
        return 0
    match = _INT_RE.search(text.replace(",", ""))
    return int(match.group(0)) if match else 0


def _extract_id_from_url(url: str) -> str:
    match = _PRESET_URL_RE.search(url)
    return match.group("id") if match else ""


def _extract_query_id(href: str | None, key: str) -> int | None:
    if not href:
        return None
    parsed = urlparse(href)
    values = parse_qs(parsed.query).get(key)
    if not values:
        return None
    return _safe_int(values[0]) or None


def _throttle(min_interval_seconds: float) -> None:
    global _last_request_ts
    with _cache_lock:
        now = monotonic()
        elapsed = now - _last_request_ts
        wait_for = max(0.0, min_interval_seconds - elapsed)
    if wait_for > 0:
        sleep(wait_for)
    with _cache_lock:
        _last_request_ts = monotonic()


def _parse_preset_card(card: Any) -> PresetsharePreset | None:
    name_link = card.select_one('a[href^="/p"]')
    if name_link is None:
        return None

    raw_href = (name_link.get("href") or "").strip()
    url = urljoin(PRESETSHARE_BASE_URL, raw_href)
    preset_id = _extract_id_from_url(raw_href or url)
    if not preset_id:
        return None

    synth_link = card.select_one('a[href*="instrument="]')
    genre_link = card.select_one('a[href*="genre="]')
    sound_type_link = card.select_one('a[href*="type="]')

    author_link = card.select_one('a[href*="/u/"], a[href*="/user/"], a[href*="/profile/"]')
    date_node = card.select_one("time, .date, .posted, .meta")

    stat_nodes = card.select(".likes, .downloads, .comments, .stat, .stats span")
    stats_text = [node.get_text(" ", strip=True) for node in stat_nodes if node.get_text(strip=True)]
    if len(stats_text) < 3:
        fallback_text = card.get_text(" ", strip=True)
        stats_text = stats_text + _INT_RE.findall(fallback_text)

    likes = _safe_int(stats_text[0] if len(stats_text) >= 1 else "0")
    downloads = _safe_int(stats_text[1] if len(stats_text) >= 2 else "0")
    comments = _safe_int(stats_text[2] if len(stats_text) >= 3 else "0")

    synth_id = _extract_query_id(synth_link.get("href") if synth_link else None, "instrument")
    genre_id = _extract_query_id(genre_link.get("href") if genre_link else None, "genre")
    sound_type_id = _extract_query_id(sound_type_link.get("href") if sound_type_link else None, "type")

    return {
        "id": preset_id,
        "name": name_link.get_text(" ", strip=True) or f"Preset {preset_id}",
        "url": url,
        "synth": synth_link.get_text(" ", strip=True) if synth_link else SYNTH_ID_TO_NAME.get(synth_id),
        "synthId": synth_id,
        "genre": genre_link.get_text(" ", strip=True) if genre_link else GENRE_ID_TO_NAME.get(genre_id),
        "genreId": genre_id,
        "soundType": sound_type_link.get_text(" ", strip=True) if sound_type_link else SOUND_TYPE_ID_TO_NAME.get(sound_type_id),
        "soundTypeId": sound_type_id,
        "author": author_link.get_text(" ", strip=True) if author_link else None,
        "authorUrl": urljoin(PRESETSHARE_BASE_URL, author_link.get("href")) if author_link and author_link.get("href") else None,
        "datePosted": date_node.get_text(" ", strip=True) if date_node else None,
        "likes": likes,
        "downloads": downloads,
        "comments": comments,
        "source": "presetshare",
    }


def _parse_list_page(html: str) -> list[PresetsharePreset]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("article, .preset-card, .preset, li, .card")
    results: list[PresetsharePreset] = []
    seen_ids: set[str] = set()
    for card in cards:
        try:
            parsed = _parse_preset_card(card)
            if not parsed:
                continue
            if parsed["id"] in seen_ids:
                continue
            seen_ids.add(parsed["id"])
            results.append(parsed)
        except Exception as exc:  # pragma: no cover
            logger.warning("PresetShare card parse failed: %s", exc)
    return results


def scrape_presets(
    *,
    instrument: int | None = None,
    genre: int | None = None,
    sound_type: int | None = None,
    page: int = 1,
    limit: int = 24,
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    min_request_interval_seconds: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS,
) -> list[PresetsharePreset]:
    current_page = max(1, page)
    max_results = max(1, limit)
    cache_key = build_cache_key(
        instrument=instrument,
        genre=genre,
        sound_type=sound_type,
        page=current_page,
    )

    now = datetime.now(UTC)
    with _cache_lock:
        entry = _cache.get(cache_key)
        if entry and entry.expires_at > now:
            return entry.data[:max_results]

    params: dict[str, Any] = {"page": current_page}
    if instrument is not None:
        params["instrument"] = instrument
    if genre is not None:
        params["genre"] = genre
    if sound_type is not None:
        params["type"] = sound_type

    _throttle(min_request_interval_seconds)
    with httpx.Client(timeout=20.0, follow_redirects=True, headers={"User-Agent": PRESETSHARE_USER_AGENT}) as client:
        response = client.get(urljoin(PRESETSHARE_BASE_URL, PRESETSHARE_PRESETS_PATH), params=params)
        response.raise_for_status()
        results = _parse_list_page(response.text)[:max_results]

    with _cache_lock:
        _cache[cache_key] = _CacheEntry(
            expires_at=now + timedelta(seconds=cache_ttl_seconds),
            data=results,
        )
    return results
