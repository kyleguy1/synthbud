from fastapi.testclient import TestClient

from app.main import app
from app.routers.meta import list_tags


client = TestClient(app)


def test_list_tags_returns_empty_list_when_no_tags():
    class EmptyResult:
        def all(self):
            return []

    class DummySession:
        def execute(self, *_args, **_kwargs):
            return EmptyResult()

    assert list_tags(db=DummySession()) == []


def test_list_preset_packs_route_returns_distinct_pack_names():
    from app import db as db_module

    class DummyResult:
        def all(self):
            return [("Factory",), ("My Bank",)]

    def dummy_get_db():
        class DummySession:
            def execute(self, *_args, **_kwargs):
                return DummyResult()

            def close(self):
                pass

        yield DummySession()

    app.dependency_overrides[db_module.get_db] = dummy_get_db
    try:
        response = client.get("/api/meta/preset-packs?source=local-filesystem&synth=Serum")
    finally:
        app.dependency_overrides.pop(db_module.get_db, None)

    assert response.status_code == 200
    assert response.json() == ["Factory", "My Bank"]


def test_list_synths_route_supports_presetshare_source():
    from app import db as db_module

    def dummy_get_db():
        class DummySession:
            def close(self):
                pass

        yield DummySession()

    app.dependency_overrides[db_module.get_db] = dummy_get_db
    try:
        response = client.get("/api/meta/synths?source=presetshare")
    finally:
        app.dependency_overrides.pop(db_module.get_db, None)

    assert response.status_code == 200
    payload = response.json()
    assert "Serum" in payload
    assert "Vital" in payload


def test_list_preset_genres_and_types_support_presetshare_source():
    response = client.get("/api/meta/preset-genres?source=presetshare")
    assert response.status_code == 200
    assert "Dubstep" in response.json()

    response = client.get("/api/meta/preset-types?source=presetshare")
    assert response.status_code == 200
    assert "Lead" in response.json()
