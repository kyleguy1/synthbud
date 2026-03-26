from fastapi.testclient import TestClient

from app.main import app


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
                    return DummyResult(params["table_name"])
                return DummyResult()

            def close(self):
                pass

        yield DummySession()

    app.dependency_overrides[db_module.get_db] = dummy_get_db

    resp = client.get("/api/health/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "app" in data


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

    resp = client.get("/api/health/")
    assert resp.status_code == 503
    assert "missing required tables" in resp.json()["detail"]
