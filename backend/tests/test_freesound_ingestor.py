from app.ingestion.freesound_ingestor import (
    extract_author,
    extract_preview_url,
    normalize_freesound_source_page_url,
)


def test_extract_preview_url_prefers_hyphenated_keys():
    payload = {
        "previews": {
            "preview-hq-mp3": "https://cdn.example.com/hq.mp3",
            "preview_hq_mp3": "https://cdn.example.com/legacy.mp3",
        }
    }

    assert extract_preview_url(payload) == "https://cdn.example.com/hq.mp3"


def test_extract_preview_url_supports_legacy_underscore_keys():
    payload = {
        "previews": {
            "preview_hq_mp3": "https://cdn.example.com/legacy.mp3",
        }
    }

    assert extract_preview_url(payload) == "https://cdn.example.com/legacy.mp3"


def test_extract_author_handles_both_shapes():
    assert extract_author({"username": "alice"}) == "alice"
    assert extract_author({"user": {"username": "bob"}}) == "bob"


def test_normalize_source_page_url_keeps_public_freesound_url():
    source_url = "https://freesound.org/people/Kai/sounds/661100"
    assert (
        normalize_freesound_source_page_url(source_url)
        == "https://freesound.org/people/Kai/sounds/661100/"
    )


def test_normalize_source_page_url_converts_api_url_to_owner_url_when_author_known():
    source_url = "https://freesound.org/apiv2/sounds/661100/"
    assert (
        normalize_freesound_source_page_url(source_url, author="Kai")
        == "https://freesound.org/people/Kai/sounds/661100/"
    )


def test_normalize_source_page_url_handles_relative_api_path():
    source_url = "/apiv2/sounds/661100/"
    assert (
        normalize_freesound_source_page_url(source_url, author="Kai")
        == "https://freesound.org/people/Kai/sounds/661100/"
    )


def test_normalize_source_page_url_builds_from_author_and_id_when_missing():
    assert (
        normalize_freesound_source_page_url(None, author="Kai", sound_id="661100")
        == "https://freesound.org/people/Kai/sounds/661100/"
    )
