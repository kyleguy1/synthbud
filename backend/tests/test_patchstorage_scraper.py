from __future__ import annotations

from app.scrapers.patchstorage import (
    PatchstoragePreset,
    _parse_patch,
    _strip_html,
    is_redistributable,
)


def _raw_patch(overrides: dict | None = None) -> dict:
    base = {
        "id": 42,
        "title": {"rendered": "Warm Pad"},
        "excerpt": {"rendered": "<p>A warm analog pad.</p>"},
        "author": {"name": "TestAuthor"},
        "platforms": [{"id": 100, "name": "Vital"}],
        "categories": [{"id": 1, "name": "Preset"}],
        "tags": [{"id": 5, "name": "pad"}, {"id": 6, "name": "ambient"}],
        "license": {"name": "Creative Commons Zero v1.0 Universal", "slug": "cc0"},
        "date": "2025-01-15T12:00:00",
        "link": "https://patchstorage.com/warm-pad/",
        "download_count": 150,
        "view_count": 800,
    }
    if overrides:
        base.update(overrides)
    return base


# --- _parse_patch ---

def test_parse_patch_extracts_basic_fields():
    p = _parse_patch(_raw_patch())
    assert p["id"] == 42
    assert p["title"] == "Warm Pad"
    assert p["author_name"] == "TestAuthor"
    assert p["url"] == "https://patchstorage.com/warm-pad/"
    assert p["source"] == "patchstorage"


def test_parse_patch_extracts_platforms_and_tags():
    p = _parse_patch(_raw_patch())
    assert p["platform_names"] == ["Vital"]
    assert p["category_names"] == ["Preset"]
    assert p["tag_names"] == ["pad", "ambient"]


def test_parse_patch_extracts_license():
    p = _parse_patch(_raw_patch())
    assert p["license_name"] == "Creative Commons Zero v1.0 Universal"
    assert p["license_slug"] == "cc0"


def test_parse_patch_extracts_counts():
    p = _parse_patch(_raw_patch())
    assert p["download_count"] == 150
    assert p["view_count"] == 800


def test_parse_patch_handles_plain_title():
    p = _parse_patch(_raw_patch({"title": "Simple Title"}))
    assert p["title"] == "Simple Title"


def test_parse_patch_strips_html_from_excerpt():
    p = _parse_patch(_raw_patch())
    assert p["excerpt"] == "A warm analog pad."


def test_parse_patch_handles_missing_author():
    p = _parse_patch(_raw_patch({"author": None}))
    assert p["author_name"] is None


def test_parse_patch_handles_missing_license():
    p = _parse_patch(_raw_patch({"license": None}))
    assert p["license_name"] is None
    assert p["license_slug"] is None


def test_parse_patch_fallback_url():
    raw = _raw_patch()
    del raw["link"]
    p = _parse_patch(raw)
    assert "42" in p["url"]


# --- is_redistributable ---

def test_redistributable_licenses():
    assert is_redistributable("cc0") is True
    assert is_redistributable("cc-by") is True
    assert is_redistributable("cc-by-sa") is True
    assert is_redistributable("gpl") is True
    assert is_redistributable("mit") is True


def test_non_redistributable():
    assert is_redistributable(None) is False
    assert is_redistributable("") is False
    assert is_redistributable("all-rights-reserved") is False


# --- _strip_html ---

def test_strip_html():
    assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"
    assert _strip_html("no tags") == "no tags"
