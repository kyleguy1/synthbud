from app.ingestion.freesound_ingestor import (
    extract_author,
    extract_preview_url,
    normalize_freesound_source_page_url,
    upsert_sound_from_payload,
)
from app.models import Sound


class FakeQuery:
    def __init__(self, session, source=None, source_sound_id=None):
        self.session = session
        self.source = source
        self.source_sound_id = source_sound_id

    def filter(self, *conditions):
        source = self.source
        source_sound_id = self.source_sound_id
        for condition in conditions:
            left_key = getattr(condition.left, "key", None)
            right_value = getattr(condition.right, "value", None)
            if left_key == "source":
                source = right_value
            if left_key == "source_sound_id":
                source_sound_id = right_value
        return FakeQuery(self.session, source=source, source_sound_id=source_sound_id)

    def first(self):
        for sound in self.session.sounds:
            if sound.source == self.source and sound.source_sound_id == self.source_sound_id:
                return sound
        return None


class FakeSession:
    def __init__(self):
        self.sounds = []

    def query(self, _model):
        return FakeQuery(self)

    def add(self, sound):
        if sound not in self.sounds:
            self.sounds.append(sound)


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


def test_upsert_sound_from_payload_stores_raw_and_canonical_tags():
    session = FakeSession()
    payload = {
        "id": 9001,
        "name": "Warm Pad",
        "tags": ["Warm Pads", "LoFi", "232hz", "Drum & Bass"],
        "duration": 1.5,
        "samplerate": 44100,
        "channels": 2,
        "license": "https://creativecommons.org/publicdomain/zero/1.0/",
        "username": "Kai",
        "url": "https://freesound.org/people/Kai/sounds/9001/",
        "download": "https://example.com/file.wav",
        "previews": {"preview-hq-mp3": "https://cdn.example.com/hq.mp3"},
    }

    sound = upsert_sound_from_payload(session, payload)

    assert isinstance(sound, Sound)
    assert sound.raw_tags == ["Warm Pads", "LoFi", "232hz", "Drum & Bass"]
    assert sound.tags == ["pad", "warm", "lo-fi", "drum-and-bass"]
