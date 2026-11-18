from fastapi.testclient import TestClient

from app.main import Settings, create_app


def test_disabled_and_unconfigured_task_api():
    with TestClient(create_app(Settings())) as client:
        assert client.get("/api/v1/tasks").status_code == 503
        assert client.post("/api/v1/tasks", json={"title": "x"}).status_code == 503
        assert client.get("/health").status_code == 200
    with TestClient(create_app(Settings(task_api_enabled=True))) as client:
        assert client.get("/api/v1/tasks").status_code == 503


def test_database_outage_is_sanitized():
    settings = Settings(
        task_api_enabled=True,
        database_url="postgresql://user:private@127.0.0.1:1/db",
        database_timeout_seconds=2,
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/tasks")
        assert response.status_code == 503
        assert "private" not in response.text
        assert client.get("/health").status_code == 200
