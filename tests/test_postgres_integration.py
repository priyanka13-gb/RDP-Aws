"""Opt-in PostgreSQL service tests, independent of Docker Compose and AWS."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import Settings, create_app, create_database_engine
from app.tasks import Base

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
        reason="Requires an isolated PostgreSQL16 service",
    ),
]


def test_postgres16_pool_and_readiness():
    settings = Settings.from_environment()
    assert settings.database_url, "Configure the isolated test database"
    engine = create_database_engine(settings)
    try:
        with engine.connect() as connection:
            database = connection.execute(text("SELECT current_database()")).scalar_one()
            assert database == "resilient_db"
            assert connection.execute(text("SHOW server_version")).scalar_one().startswith("16.")
        assert engine.pool.checkedout() == 0
    finally:
        engine.dispose()
    with TestClient(create_app(settings)) as client:
        for endpoint in ["/health", "/ready", "/version", "/metrics"]:
            assert client.get(endpoint).status_code == 200
        assert client.get("/ready").json() == {"status": "ready"}


def test_unreachable_database_preserves_liveness():
    settings = Settings(
        database_url="postgresql://unavailable@127.0.0.1:1/unavailable", database_timeout_seconds=2
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/ready").status_code == 503
        assert client.get("/health").status_code == 200


def test_task_crud_and_persistence():
    settings = Settings.from_environment()
    settings = Settings(
        database_url=settings.database_url,
        database_password_file=settings.database_password_file,
        task_api_enabled=True,
    )
    engine = create_database_engine(settings)
    Base.metadata.create_all(engine)
    engine.dispose()
    prefix = f"test-{uuid.uuid4()}"
    ids = []
    try:
        with TestClient(create_app(settings)) as client:
            assert client.post("/api/v1/tasks", json={"title": "  "}).status_code == 422
            assert (
                client.post("/api/v1/tasks", json={"title": "x", "status": "bad"}).status_code
                == 422
            )
            response = client.post("/api/v1/tasks", json={"title": prefix, "description": "first"})
            assert response.status_code == 201
            task = response.json()
            ids.append(task["id"])
            assert task["status"] == "pending"
            assert task["created_at"].endswith(("Z", "+00:00"))
            assert task["updated_at"].endswith(("Z", "+00:00"))
            second = client.post(
                "/api/v1/tasks", json={"title": prefix + "-2", "status": "completed"}
            ).json()
            ids.append(second["id"])
            assert client.get("/api/v1/tasks/" + ids[0]).json()["title"] == prefix
            updated = client.patch(
                "/api/v1/tasks/" + ids[0],
                json={"title": prefix + "-updated", "status": "in_progress"},
            )
            assert updated.status_code == 200
            assert updated.json()["status"] == "in_progress"
            assert updated.json()["title"] == prefix + "-updated"
            assert client.patch("/api/v1/tasks/" + ids[0], json={"status": None}).status_code == 422
            filtered = client.get("/api/v1/tasks", params={"status": "in_progress"}).json()
            assert ids[0] in [item["id"] for item in filtered]
            page = client.get("/api/v1/tasks", params={"limit": 1, "offset": 0}).json()
            next_page = client.get("/api/v1/tasks", params={"limit": 1, "offset": 1}).json()
            assert len(page) == len(next_page) == 1 and page[0]["id"] != next_page[0]["id"]
            assert client.get("/api/v1/tasks/not-a-uuid").status_code == 422
            assert client.get("/api/v1/tasks/" + str(uuid.uuid4())).status_code == 404
        with TestClient(create_app(settings)) as restarted:
            assert restarted.get("/api/v1/tasks/" + ids[0]).json()["title"] == prefix + "-updated"
            assert restarted.delete("/api/v1/tasks/" + ids[0]).status_code == 204
            assert restarted.get("/api/v1/tasks/" + ids[0]).status_code == 404
    finally:
        with TestClient(create_app(settings)) as cleanup:
            for task_id in ids:
                cleanup.delete("/api/v1/tasks/" + task_id)
