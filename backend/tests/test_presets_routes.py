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
        parameters = SimpleNamespace(raw_payload=None)

        class DummySession:
            def execute(self, statement):
                statement_text = str(statement).lower()
                if "count(" in statement_text:
                    return DummyResult(scalar_value=1)
                return DummyResult(rows=[(preset, pack, source, parameters)])

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
        "has_next": False,
    }


def test_list_presets_presetshare_source(monkeypatch):
    from app.routers import presets as presets_router

    def fake_scrape_presets_window(**_kwargs):
        return (
            [
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
            ],
            True,
        )

    monkeypatch.setattr(presets_router, "scrape_presets_window", fake_scrape_presets_window)

    response = client.get("/api/presets/?source=presetshare&page=1&page_size=20")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["has_next"] is True
    assert payload["items"][0]["name"] == "Neuro Lead"
    assert payload["items"][0]["source_key"] == "presetshare"
    assert payload["items"][0]["author_url"] == "https://presetshare.com/u/presetuser"
    assert payload["items"][0]["posted_label"] == "Today"
    assert payload["items"][0]["like_count"] == 10
    assert payload["items"][0]["download_count"] == 200
    assert payload["items"][0]["comment_count"] == 3


def test_list_presets_presetshare_source_supports_metric_sorting(monkeypatch):
    from app.routers import presets as presets_router

    def fake_scrape_presets_window(**_kwargs):
        return (
            [
                {
                    "id": "100",
                    "name": "Lower Likes",
                    "url": "https://presetshare.com/p100",
                    "synth": "Vital",
                    "author": "user-a",
                    "authorUrl": "https://presetshare.com/u/user-a",
                    "datePosted": "Today",
                    "likes": 4,
                    "downloads": 300,
                    "comments": 0,
                    "source": "presetshare",
                },
                {
                    "id": "101",
                    "name": "Higher Likes",
                    "url": "https://presetshare.com/p101",
                    "synth": "Vital",
                    "author": "user-b",
                    "authorUrl": "https://presetshare.com/u/user-b",
                    "datePosted": "Today",
                    "likes": 18,
                    "downloads": 120,
                    "comments": 1,
                    "source": "presetshare",
                },
            ],
            False,
        )

    monkeypatch.setattr(presets_router, "scrape_presets_window", fake_scrape_presets_window)

    response = client.get("/api/presets/?source=presetshare&sort=most-liked&page=1&page_size=20")
    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload["items"]] == ["Higher Likes", "Lower Likes"]


def test_sync_route_supports_presetshare_index(monkeypatch):
    from app.routers import presets as presets_router

    monkeypatch.setattr(
        presets_router,
        "ingest_presetshare_index",
        lambda max_pages: {
            "source": "presetshare-index",
            "requested_pages": max_pages,
            "scanned_pages": 3,
            "ingested_count": 72,
        },
    )

    response = client.post("/api/presets/sync?source=presetshare-index&max_pages=3")
    assert response.status_code == 200
    assert response.json() == {
        "source": "presetshare-index",
        "requested_pages": 3,
        "scanned_pages": 3,
        "ingested_count": 72,
    }


def test_list_presets_route_exposes_indexed_remote_metadata():
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
            id=11,
            name="Indexed Pad",
            author="cataloguser",
            synth_name="Serum",
            synth_vendor=None,
            tags=["Synthwave", "Pad"],
            visibility=PresetVisibilityEnum.PUBLIC,
            is_redistributable=True,
            parse_status=PresetParseStatusEnum.PARTIAL,
            source_url="https://presetshare.com/p201",
        )
        pack = SimpleNamespace(
            id=77,
            name="Serum Presets",
            author=None,
            synth_name="Serum",
            synth_vendor=None,
            source_url="https://presetshare.com",
            license_label=None,
            is_redistributable=True,
            visibility=PresetVisibilityEnum.PUBLIC,
        )
        source = SimpleNamespace(key="presetshare-index")
        parameters = SimpleNamespace(
            raw_payload={
                "authorUrl": "https://presetshare.com/@cataloguser",
                "datePosted": "Yesterday",
                "likes": 3,
                "downloads": 44,
                "comments": 1,
            }
        )

        class DummySession:
            def execute(self, statement):
                statement_text = str(statement).lower()
                if "count(" in statement_text:
                    return DummyResult(scalar_value=1)
                return DummyResult(rows=[(preset, pack, source, parameters)])

            def close(self):
                pass

        yield DummySession()

    app.dependency_overrides[db_module.get_db] = dummy_get_db
    try:
        response = client.get("/api/presets/?source=presetshare-index&page=1&page_size=20")
    finally:
        app.dependency_overrides.pop(db_module.get_db, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["source_key"] == "presetshare-index"
    assert payload["items"][0]["author_url"] == "https://presetshare.com/@cataloguser"
    assert payload["items"][0]["posted_label"] == "Yesterday"
    assert payload["items"][0]["like_count"] == 3


def test_list_presets_route_sorts_indexed_results_by_downloads():
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
        rows = [
            (
                SimpleNamespace(
                    id=11,
                    name="Lower Downloads",
                    author="cataloguser",
                    synth_name="Serum",
                    synth_vendor=None,
                    tags=["Synthwave"],
                    visibility=PresetVisibilityEnum.PUBLIC,
                    is_redistributable=True,
                    parse_status=PresetParseStatusEnum.PARTIAL,
                    source_url="https://presetshare.com/p201",
                    imported_at=1,
                ),
                SimpleNamespace(
                    id=77,
                    name="Serum Presets",
                    author=None,
                    synth_name="Serum",
                    synth_vendor=None,
                    source_url="https://presetshare.com",
                    license_label=None,
                    is_redistributable=True,
                    visibility=PresetVisibilityEnum.PUBLIC,
                ),
                SimpleNamespace(key="presetshare-index"),
                SimpleNamespace(raw_payload={"downloads": 44}),
            ),
            (
                SimpleNamespace(
                    id=12,
                    name="Higher Downloads",
                    author="cataloguser",
                    synth_name="Serum",
                    synth_vendor=None,
                    tags=["Synthwave"],
                    visibility=PresetVisibilityEnum.PUBLIC,
                    is_redistributable=True,
                    parse_status=PresetParseStatusEnum.PARTIAL,
                    source_url="https://presetshare.com/p202",
                    imported_at=2,
                ),
                SimpleNamespace(
                    id=78,
                    name="Serum Presets",
                    author=None,
                    synth_name="Serum",
                    synth_vendor=None,
                    source_url="https://presetshare.com",
                    license_label=None,
                    is_redistributable=True,
                    visibility=PresetVisibilityEnum.PUBLIC,
                ),
                SimpleNamespace(key="presetshare-index"),
                SimpleNamespace(raw_payload={"downloads": 144}),
            ),
        ]

        class DummySession:
            def execute(self, *_args, **_kwargs):
                return DummyResult(rows=rows)

            def close(self):
                pass

        yield DummySession()

    app.dependency_overrides[db_module.get_db] = dummy_get_db
    try:
        response = client.get("/api/presets/?source=presetshare-index&sort=most-downloaded&page=1&page_size=20")
    finally:
        app.dependency_overrides.pop(db_module.get_db, None)

    assert response.status_code == 200
    payload = response.json()
    assert [item["name"] for item in payload["items"]] == ["Higher Downloads", "Lower Downloads"]


def test_cache_bust_route_rejects_unknown_source():
    response = client.post("/api/presets/cache-bust?source=unknown")
    assert response.status_code == 400
