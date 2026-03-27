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

        class DummySession:
            def execute(self, statement):
                statement_text = str(statement).lower()
                if "count(" in statement_text:
                    return DummyResult(scalar_value=1)
                return DummyResult(rows=[(preset, pack)])

            def close(self):
                pass

        yield DummySession()

    app.dependency_overrides[db_module.get_db] = dummy_get_db
    try:
        response = client.get("/api/presets/?page=1&page_size=20")
    finally:
        app.dependency_overrides.pop(db_module.get_db, None)

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": 1,
                "name": "Glass Keys",
                "author": "Synthbud",
                "synth_name": "Serum",
                "synth_vendor": "Xfer",
                "tags": ["keys", "bright"],
                "visibility": "public",
                "is_redistributable": True,
                "parse_status": "success",
                "source_url": "https://example.com/presets/glass-keys",
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
                },
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 20,
    }
