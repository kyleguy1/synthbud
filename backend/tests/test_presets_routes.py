from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.models import PresetParseStatusEnum, PresetVisibilityEnum


client = TestClient(app)


def test_list_presets_route_is_available():
    from app import db as db_module

    class DummyResult:
        def __init__(self, *, scalar_value=None, rows=None):
            self.scalar_value = scalar_value
            self.rows = rows or []

        def scalar_one(self):
            return self.scalar_value

        def all(self):
            return self.rows

    def dummy_get_db():
        preset = SimpleNamespace(
            id=1,
            name="Glass Keys",
            author="Synthbud",
            synth_name="Serum",
            synth_vendor="Xfer",
            tags=["keys", "bright"],
            visibility=PresetVisibilityEnum.PUBLIC,
            is_redistributable=True,
            parse_status=PresetParseStatusEnum.SUCCESS,
            source_url="https://example.com/presets/glass-keys",
        )
        pack = SimpleNamespace(
            id=10,
            name="Starter Pack",
            author="Synthbud",
            synth_name="Serum",
            synth_vendor="Xfer",
            source_url="https://example.com/packs/starter-pack",
            license_label="CC0",
            is_redistributable=True,
            visibility=PresetVisibilityEnum.PUBLIC,
        )
        source = SimpleNamespace(key="local-filesystem")

        class DummySession:
            def execute(self, statement):
                statement_text = str(statement).lower()
                if "count(" in statement_text:
                    return DummyResult(scalar_value=1)
                return DummyResult(rows=[(preset, pack, source)])

            def close(self):
                pass

        yield DummySession()

    app.dependency_overrides[db_module.get_db] = dummy_get_db
    try:
        response = client.get("/api/presets/?source=local-filesystem&pack=Starter%20Pack&page=1&page_size=20")
    finally:
        app.dependency_overrides.pop(db_module.get_db, None)

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": 1,
                "name": "Glass Keys",
                "author": "Synthbud",
                "author_url": None,
                "synth_name": "Serum",
                "synth_vendor": "Xfer",
                "tags": ["keys", "bright"],
                "visibility": "public",
                "is_redistributable": True,
                "parse_status": "success",
                "source_url": "https://example.com/presets/glass-keys",
                "source_key": "local-filesystem",
                "posted_label": None,
                "like_count": None,
                "download_count": None,
                "comment_count": None,
                "pack": {
                    "id": 10,
                    "name": "Starter Pack",
                    "author": "Synthbud",
                    "synth_name": "Serum",
                    "synth_vendor": "Xfer",
                    "source_url": "https://example.com/packs/starter-pack",
                    "license_label": "CC0",
                    "is_redistributable": True,
                    "visibility": "public",
                    "source_key": "local-filesystem",
                },
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 20,
    }


def test_list_presets_presetshare_source(monkeypatch):
    from app.routers import presets as presets_router

    def fake_scrape_presets(**_kwargs):
        return [
            {
                "id": "19753",
                "name": "Neuro Lead",
                "url": "https://presetshare.com/p19753",
                "synth": "Vital",
                "synthId": 2,
                "genre": "Dubstep",
                "genreId": 3,
                "soundType": "Lead",
                "soundTypeId": 11,
                "author": "presetuser",
                "authorUrl": "https://presetshare.com/u/presetuser",
                "datePosted": "Today",
                "likes": 10,
                "downloads": 200,
                "comments": 3,
                "source": "presetshare",
            }
        ]

    monkeypatch.setattr(presets_router, "scrape_presets", fake_scrape_presets)

    response = client.get("/api/presets/?source=presetshare&page=1&page_size=20")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "Neuro Lead"
    assert payload["items"][0]["source_key"] == "presetshare"
    assert payload["items"][0]["author_url"] == "https://presetshare.com/u/presetuser"
    assert payload["items"][0]["posted_label"] == "Today"
    assert payload["items"][0]["like_count"] == 10
    assert payload["items"][0]["download_count"] == 200
    assert payload["items"][0]["comment_count"] == 3


def test_cache_bust_route_rejects_unknown_source():
    response = client.post("/api/presets/cache-bust?source=unknown")
    assert response.status_code == 400
