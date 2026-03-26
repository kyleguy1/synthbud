from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_cors_preflight_allows_vite_origin():
    response = client.options(
        "/api/health/",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
