"""Opt-in checks against a running Compose stack; never remove volumes."""

import os
import subprocess
from pathlib import Path

import httpx
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DOCKER_INTEGRATION") != "1",
        reason="Set RUN_DOCKER_INTEGRATION=1 after docker compose up -d --wait",
    ),
]
ROOT = Path(__file__).resolve().parents[1]


def test_real_postgresql_connection_from_app_container():
    code = (
        "from app.main import Settings, create_database_engine; "
        "from sqlalchemy import text; "
        "engine = create_database_engine(Settings.from_environment()); "
        "connection = engine.connect(); "
        "assert connection.execute(text('SELECT current_database()')).scalar_one() "
        "== 'resilient_db'; "
        "assert connection.execute(text('SHOW server_version')).scalar_one().startswith('16.'); "
        "connection.close(); engine.dispose()"
    )
    result = subprocess.run(
        ["docker", "compose", "exec", "-T", "app", "python", "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, "Container PostgreSQL connectivity check failed"


def test_compose_http_endpoints():
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=15) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "healthy"}
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json() == {"status": "ready"}
        version = client.get("/version")
        assert version.status_code == 200
        assert {"app_version", "git_sha"} <= version.json().keys()
        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "http_requests_total" in metrics.text
