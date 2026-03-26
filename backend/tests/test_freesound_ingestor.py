from app.ingestion.freesound_ingestor import extract_author, extract_preview_url


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
