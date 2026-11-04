import json
import logging
from unittest.mock import MagicMock

import psycopg
import pytest
from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families
from sqlalchemy.exc import TimeoutError as PoolTimeout

from app.main import JsonFormatter, Settings, create_app, create_database_engine


@pytest.fixture
def client():
    with TestClient(create_app(Settings())) as test_client:
        yield test_client


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "project": "Resilient Delivery Platform on AWS",
        "environment": "development",
    }


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_readiness_without_database(client, monkeypatch):
    def unexpected_connection(*args, **kwargs):
        pytest.fail("Database should not be contacted when unconfigured")

    monkeypatch.setattr("app.main.create_database_engine", unexpected_connection)
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_version_from_environment(monkeypatch):
    monkeypatch.setenv("APP_VERSION", "2.4.1")
    monkeypatch.setenv("GIT_SHA", "abc1234")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_PASSWORD_FILE", raising=False)
    monkeypatch.delenv("DATABASE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/version")
        assert response.status_code == 200
        assert response.json() == {"app_version": "2.4.1", "git_sha": "abc1234"}
        assert client.get("/").json()["environment"] == "test"


def test_metrics(client):
    client.get("/health")
    client.get("/health")
    response = client.get("/metrics", follow_redirects=False)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    samples = [
        sample
        for family in text_string_to_metric_families(response.text)
        for sample in family.samples
    ]
    counter = next(
        s for s in samples if s.name == "http_requests_total" and s.labels["route"] == "/health"
    )
    assert counter.labels == {"method": "GET", "route": "/health", "status": "200"}
    assert counter.value == 2
    count = next(
        s
        for s in samples
        if s.name == "http_request_duration_seconds_count" and s.labels["route"] == "/health"
    )
    assert count.value == 2
    assert any(s.name == "http_request_duration_seconds_bucket" for s in samples)


@pytest.mark.parametrize("error", [psycopg.OperationalError, PoolTimeout])
def test_database_dependency_failure(monkeypatch, capsys, error):
    engine = MagicMock()
    engine.connect.side_effect = error("sensitive-driver-detail")
    monkeypatch.setattr("app.main.create_database_engine", lambda settings: engine)
    with TestClient(create_app(Settings(database_url="postgresql://localhost/example"))) as client:
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {
            "status": "not_ready",
            "dependencies": {"postgresql": "unavailable"},
        }
        assert client.get("/health").status_code == 200
        assert "sensitive-driver-detail" not in response.text + capsys.readouterr().err


def test_database_ready_and_connection_closed(monkeypatch):
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = 1
    monkeypatch.setattr("app.main.create_database_engine", lambda settings: engine)
    settings = Settings(database_url="postgresql://localhost/example")
    with TestClient(create_app(settings)) as client:
        assert client.get("/ready").status_code == 200
        assert client.get("/ready").status_code == 200
    assert engine.connect.call_count == 2
    assert str(connection.execute.call_args.args[0]) == "SELECT 1"
    assert engine.connect.return_value.__exit__.call_count == 2
    engine.dispose.assert_called_once()


def test_query_failure_returns_connection(monkeypatch):
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.side_effect = psycopg.OperationalError("query failed")
    monkeypatch.setattr("app.main.create_database_engine", lambda settings: engine)
    with TestClient(create_app(Settings(database_url="postgresql://localhost/example"))) as client:
        assert client.get("/ready").status_code == 503
    engine.connect.return_value.__exit__.assert_called_once()
    engine.dispose.assert_called_once()


def test_pool_configuration_and_secret(monkeypatch, tmp_path):
    secret = tmp_path / "password"
    secret.write_text("test-only-special:@/password", encoding="utf-8")
    factory = MagicMock()
    monkeypatch.setattr("app.main.create_engine", factory)
    create_database_engine(
        Settings(
            database_url="postgresql://resilient_user@db:5432/resilient_db",
            database_password_file=str(secret),
        )
    )
    url = factory.call_args.args[0]
    options = factory.call_args.kwargs
    assert url.host == "db"
    assert url.drivername == "postgresql+psycopg"
    assert url.password == secret.read_text(encoding="utf-8")
    assert options["pool_size"] == 5
    assert options["max_overflow"] == 0
    assert options["pool_timeout"] == 3
    assert options["pool_pre_ping"] is True
    assert options["connect_args"]["connect_timeout"] == 3
    assert options["connect_args"]["options"] == "-c statement_timeout=3000"


def test_missing_secret_fails_without_exposing_configuration(tmp_path):
    with pytest.raises(ValueError) as error:
        create_database_engine(
            Settings(
                database_url="postgresql://user:sensitive-value@db/example",
                database_password_file=str(tmp_path / "missing"),
            )
        )
    assert "sensitive-value" not in str(error.value)


def test_unmatched_paths_have_bounded_metric_labels(client):
    client.get("/unknown-one?token=private")
    client.get("/unknown-two")
    metrics = client.get("/metrics").text
    assert 'route="unmatched",status="404"} 2.0' in metrics
    assert "unknown-one" not in metrics
    assert "private" not in metrics


def test_json_log_formatter():
    record = logging.LogRecord(
        "delivery_platform", logging.INFO, __file__, 1, "http_request", (), None
    )
    record.status_code = 200
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["message"] == "http_request"
    assert payload["status_code"] == 200
    assert payload["timestamp"].endswith("+00:00")


@pytest.mark.parametrize("value", ["0", "31", "invalid"])
def test_invalid_database_timeout(monkeypatch, value):
    monkeypatch.setenv("DATABASE_TIMEOUT_SECONDS", value)
    with pytest.raises(ValueError):
        Settings.from_environment()
