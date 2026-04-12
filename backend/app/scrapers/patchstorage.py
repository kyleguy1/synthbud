from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from time import monotonic, sleep
from typing import Any, TypedDict
import logging

import httpx


logger = logging.getLogger(__name__)

PATCHSTORAGE_BASE_URL = "https://patchstorage.com"
PATCHSTORAGE_API_URL = f"{PATCHSTORAGE_BASE_URL}/api/alpha"
PATCHSTORAGE_USER_AGENT = (
    "synthbud/0.1 (https://github.com/kyleguy1/synthbud)"
)
DEFAULT_CACHE_TTL_SECONDS = 3600
DEFAULT_MIN_REQUEST_INTERVAL_SECONDS = 0.5
DEFAULT_PER_PAGE = 50

# Well-known platform IDs on Patchstorage. Looked up lazily via
# resolve_platform_id() when not present here.
_KNOWN_PLATFORM_IDS: dict[str, int] = {}

# License slugs that allow redistribution.
_REDISTRIBUTABLE_LICENSES = frozenset(
    {
        "cc0",
        "cc-by",
        "cc-by-sa",
        "cc-by-nc",
        "cc-by-nc-sa",
        "gpl",
        "mit",
        "apache",
    }
)


class PatchstoragePreset(TypedDict):
    id: int
    title: str
    excerpt: str
    author_name: str | None
    platform_names: list[str]
    category_names: list[str]
    tag_names: list[str]
    license_name: str | None
    license_slug: str | None
    date_created: str | None
    url: str
    download_count: int
    view_count: int
    source: str


# ---------------------------------------------------------------------------
# Thread-safe request cache (same pattern as presetshare.py)
# ---------------------------------------------------------------------------

@dataclass
class _CacheEntry:
    expires_at: datetime
    data: list[PatchstoragePreset]


_cache_lock = Lock()
_cache: dict[str, _CacheEntry] = {}
_last_request_ts = 0.0


def _build_cache_key(*, platform_id: int | None, page: int, per_page: int) -> str:
    return f"patchstorage:{platform_id}:{page}:{per_page}"


def clear_cache(key: str | None = None) -> int:
    with _cache_lock:
        if key is not None:
            return 1 if _cache.pop(key, None) is not None else 0
        removed = len(_cache)
        _cache.clear()
        return removed


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


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _http_client() -> httpx.Client:
    return httpx.Client(
        timeout=20.0,
        follow_redirects=True,
        headers={"User-Agent": PATCHSTORAGE_USER_AGENT},
    )


def is_redistributable(license_slug: str | None) -> bool:
    if not license_slug:
        return False
    return license_slug.strip().lower() in _REDISTRIBUTABLE_LICENSES


def resolve_platform_id(
    platform_name: str,
    *,
    min_request_interval_seconds: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS,
) -> int | None:
    key = platform_name.strip().lower()
    if key in _KNOWN_PLATFORM_IDS:
        return _KNOWN_PLATFORM_IDS[key]

    _throttle(min_request_interval_seconds)
    try:
        with _http_client() as client:
            resp = client.get(
                f"{PATCHSTORAGE_API_URL}/platforms",
                params={"search": platform_name},
            )
            resp.raise_for_status()
            results = resp.json()
    except Exception:
        logger.warning("Failed to resolve Patchstorage platform '%s'", platform_name, exc_info=True)
        return None

    if not isinstance(results, list):
        results = results.get("results", []) if isinstance(results, dict) else []

    for item in results:
        item_name = (item.get("name") or item.get("title") or "").strip().lower()
        item_id = item.get("id")
        if item_name and item_id is not None:
            _KNOWN_PLATFORM_IDS[item_name] = int(item_id)
            if item_name == key:
                return int(item_id)

    return _KNOWN_PLATFORM_IDS.get(key)


def _parse_patch(raw: dict[str, Any]) -> PatchstoragePreset:
    author_obj = raw.get("author") or {}
    author_name = author_obj.get("name") if isinstance(author_obj, dict) else None

    platform_names = [
        p.get("name") or p.get("title") or ""
        for p in (raw.get("platforms") or [])
        if isinstance(p, dict)
    ]
    category_names = [
        c.get("name") or c.get("title") or ""
        for c in (raw.get("categories") or [])
        if isinstance(c, dict)
    ]
    tag_names = [
        t.get("name") or t.get("title") or ""
        for t in (raw.get("tags") or [])
        if isinstance(t, dict)
    ]

    license_obj = raw.get("license") or {}
    license_name = license_obj.get("name") if isinstance(license_obj, dict) else None
    license_slug = license_obj.get("slug") if isinstance(license_obj, dict) else None

    patch_url = (
        raw.get("link")
        or raw.get("url")
        or f"{PATCHSTORAGE_BASE_URL}/?p={raw.get('id', '')}"
    )

    return PatchstoragePreset(
        id=int(raw.get("id") or 0),
        title=(raw.get("title", {}).get("rendered", "") if isinstance(raw.get("title"), dict) else raw.get("title", "")) or f"Patch {raw.get('id', '')}",
        excerpt=_strip_html(
            (raw.get("excerpt", {}).get("rendered", "") if isinstance(raw.get("excerpt"), dict) else raw.get("excerpt", ""))
        ),
        author_name=author_name,
        platform_names=platform_names,
        category_names=category_names,
        tag_names=tag_names,
        license_name=license_name,
        license_slug=license_slug,
        date_created=raw.get("date") or raw.get("date_created"),
        url=patch_url,
        download_count=int(raw.get("download_count") or 0),
        view_count=int(raw.get("view_count") or 0),
        source="patchstorage",
    )


def _strip_html(text: str) -> str:
    """Remove simple HTML tags from excerpt strings."""
    import re
    return re.sub(r"<[^>]+>", "", text).strip()


# ---------------------------------------------------------------------------
# Public scraping API
# ---------------------------------------------------------------------------

def fetch_patches_page(
    *,
    platform_id: int | None = None,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    min_request_interval_seconds: float = DEFAULT_MIN_REQUEST_INTERVAL_SECONDS,
) -> tuple[list[PatchstoragePreset], bool]:
    """Fetch one page of patches from Patchstorage.

    Returns (items, has_next).
    """
    current_page = max(1, page)
    cache_key = _build_cache_key(platform_id=platform_id, page=current_page, per_page=per_page)

    now = datetime.now(UTC)
    with _cache_lock:
        entry = _cache.get(cache_key)
        if entry and entry.expires_at > now:
            has_next = len(entry.data) >= per_page
            return entry.data[:], has_next

    params: dict[str, Any] = {
        "page": current_page,
        "per_page": per_page,
    }
    if platform_id is not None:
        params["platforms"] = platform_id

    _throttle(min_request_interval_seconds)
    with _http_client() as client:
        resp = client.get(f"{PATCHSTORAGE_API_URL}/patches", params=params)
        resp.raise_for_status()
        body = resp.json()

    # API may return bare list or { results: [...] }
    raw_list: list[dict] = body if isinstance(body, list) else body.get("results", [])

    results = []
    for raw in raw_list:
        try:
            results.append(_parse_patch(raw))
        except Exception as exc:
            logger.warning("Failed to parse Patchstorage patch: %s", exc)

    with _cache_lock:
        _cache[cache_key] = _CacheEntry(
            expires_at=now + timedelta(seconds=cache_ttl_seconds),
            data=results,
        )

    has_next = len(results) >= per_page
    return results, has_next
