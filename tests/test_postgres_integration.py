"""Opt-in PostgreSQL service tests, independent of Docker Compose and AWS."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import Settings, create_app, create_database_engine

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_POSTGRES_INTEGRATION") != "1",
                       reason="Requires an isolated PostgreSQL16 service"),
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
    settings = Settings(database_url="postgresql://unavailable@127.0.0.1:1/unavailable",
                        database_timeout_seconds=2)
    with TestClient(create_app(settings)) as client:
        assert client.get("/ready").status_code == 503
        assert client.get("/health").status_code == 200
