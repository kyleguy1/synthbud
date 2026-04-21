from fastapi.testclient import TestClient

from app.main import app
from app.routers import health as health_router


client = TestClient(app)


def test_health_ok(monkeypatch):
    # Monkeypatch DB dependency to avoid real DB requirement in this smoke test
    from app import db as db_module

    class DummyResult:
        def __init__(self, value=None):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    def dummy_get_db():
        class DummySession:
            def execute(self, query, params=None):
                sql = str(query)
                if "to_regclass" in sql:
                    if params["table_name"] == "public.alembic_version":
                        return DummyResult("public.alembic_version")
                    return DummyResult(params["table_name"])
                if "version_num FROM alembic_version" in sql:
                    return DummyResult("test-head")
                return DummyResult()

            def close(self):
                pass

        yield DummySession()

    app.dependency_overrides[db_module.get_db] = dummy_get_db
    monkeypatch.setattr(health_router, "_get_expected_db_revision", lambda: "test-head")

    try:
        resp = client.get("/api/health/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "app" in data
    finally:
        app.dependency_overrides.pop(db_module.get_db, None)


def test_health_reports_missing_tables(monkeypatch):
    from app import db as db_module

    class DummyResult:
        def __init__(self, value=None):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    def dummy_get_db():
        class DummySession:
            def execute(self, query, params=None):
                sql = str(query)
                if "to_regclass" in sql:
                    return DummyResult(None)
                return DummyResult()

            def close(self):
                pass

        yield DummySession()

    app.dependency_overrides[db_module.get_db] = dummy_get_db
    monkeypatch.setattr(health_router, "_get_expected_db_revision", lambda: "test-head")

    try:
        resp = client.get("/api/health/")
        assert resp.status_code == 503
        assert "missing required tables" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(db_module.get_db, None)


def test_health_reports_outdated_revision(monkeypatch):
    from app import db as db_module

    class DummyResult:
        def __init__(self, value=None):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    def dummy_get_db():
        class DummySession:
            def execute(self, query, params=None):
                sql = str(query)
                if "to_regclass" in sql:
                    return DummyResult(params["table_name"])
                if "version_num FROM alembic_version" in sql:
                    return DummyResult("0004_preset_file_hash_index")
                return DummyResult()

            def close(self):
                pass

        yield DummySession()

    app.dependency_overrides[db_module.get_db] = dummy_get_db
    monkeypatch.setattr(health_router, "_get_expected_db_revision", lambda: "0005_raw_tag_taxonomy")

    try:
        resp = client.get("/api/health/")
        assert resp.status_code == 503
        assert "out of date" in resp.json()["detail"]
        assert "0005_raw_tag_taxonomy" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(db_module.get_db, None)
