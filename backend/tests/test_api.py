from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_route():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_expected_api_routes_are_registered():
    paths = set(app.openapi()["paths"])

    assert {
        "/health",
        "/health/database",
        "/api/chat",
        "/api/v1/transcribe",
        "/api/v1/shopping/missions/vision",
    }.issubset(paths)
