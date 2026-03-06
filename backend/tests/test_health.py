from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_ok(monkeypatch):
    # Monkeypatch DB dependency to avoid real DB requirement in this smoke test
    from app import db as db_module

    def dummy_get_db():
        class DummySession:
            def execute(self, *_args, **_kwargs):
                return None

            def close(self):
                pass

        yield DummySession()

    app.dependency_overrides[db_module.get_db] = dummy_get_db

    resp = client.get("/api/health/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "app" in data

