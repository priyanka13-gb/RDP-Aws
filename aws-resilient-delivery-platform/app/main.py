"""HTTP service, dependency readiness, JSON logs, and Prometheus instrumentation."""

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError


@dataclass(frozen=True)
class Settings:
    app_version: str = "0.1.0"
    git_sha: str = "unknown"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str | None = field(default=None, repr=False)
    database_password_file: str | None = field(default=None, repr=False)
    database_timeout_seconds: int = 3

    @classmethod
    def from_environment(cls) -> "Settings":
        timeout = int(os.getenv("DATABASE_TIMEOUT_SECONDS", "3"))
        if not 2 <= timeout <= 30:
            raise ValueError("DATABASE_TIMEOUT_SECONDS must be between 2 and 30")
        level = os.getenv("LOG_LEVEL", "INFO").upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL must be a standard logging level")
        return cls(
            app_version=os.getenv("APP_VERSION", "0.1.0"),
            git_sha=os.getenv("GIT_SHA", "unknown"),
            environment=os.getenv("APP_ENV", "development"),
            log_level=level,
            database_url=os.getenv("DATABASE_URL") or None,
            database_password_file=os.getenv("DATABASE_PASSWORD_FILE") or None,
            database_timeout_seconds=timeout,
        )


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("method", "route", "status_code", "duration_seconds", "dependency"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload)


def configure_logging(level: str) -> logging.Logger:
    logger = logging.getLogger("delivery_platform")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def create_database_engine(settings: Settings) -> Engine:
    """Create a lazy, bounded pool. No connection is attempted at startup."""
    try:
        url = make_url(settings.database_url)
        if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
            raise ValueError("Unsupported database driver")
        url = url.set(drivername="postgresql+psycopg")
        if settings.database_password_file:
            password = Path(settings.database_password_file).read_text(encoding="utf-8").strip()
            if not password:
                raise ValueError("Empty database password file")
            url = url.set(password=password)
        return create_engine(
            url,
            pool_size=5,
            max_overflow=0,
            pool_timeout=settings.database_timeout_seconds,
            pool_pre_ping=True,
            pool_recycle=300,
            echo=False,
            hide_parameters=True,
            connect_args={
                "connect_timeout": settings.database_timeout_seconds,
                "options": f"-c statement_timeout={settings.database_timeout_seconds * 1000}",
            },
        )
    except (ValueError, OSError, SQLAlchemyError):
        raise ValueError("Invalid database configuration or unreadable password secret") from None


def check_database(engine: Engine) -> None:
    """Return the connection to the pool even when the probe fails."""
    with engine.connect() as connection:
        if connection.execute(text("SELECT 1")).scalar_one() != 1:
            raise ValueError("Unexpected database probe result")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    logger = configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        engine = create_database_engine(settings) if settings.database_url else None
        application.state.database_engine = engine
        try:
            yield
        finally:
            if engine is not None:
                engine.dispose()

    application = FastAPI(
        title="Resilient Delivery Platform on AWS", version=settings.app_version, lifespan=lifespan
    )
    application.state.settings = settings
    registry = CollectorRegistry()
    requests = Counter(
        "http_requests_total",
        "Completed HTTP requests",
        ["method", "route", "status"],
        registry=registry,
    )
    latency = Histogram(
        "http_request_duration_seconds",
        "HTTP request duration",
        ["method", "route"],
        registry=registry,
    )

    @application.middleware("http")
    async def instrument_request(request: Request, call_next):
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            duration = time.perf_counter() - started
            route = getattr(request.scope.get("route"), "path", "unmatched")
            method = (
                request.method
                if request.method
                in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "CONNECT"}
                else "OTHER"
            )
            requests.labels(method, route, str(status)).inc()
            latency.labels(method, route).observe(duration)
            logger.info(
                "http_request",
                extra={
                    "method": method,
                    "route": route,
                    "status_code": status,
                    "duration_seconds": round(duration, 6),
                },
            )

    @application.get("/")
    def root():
        return {"project": application.title, "environment": settings.environment}

    @application.get("/health")
    def health():
        return {"status": "healthy"}

    @application.get("/ready")
    def ready():
        # Sync endpoint runs in FastAPI's thread pool, keeping the event loop responsive.
        if settings.database_url:
            try:
                check_database(application.state.database_engine)
            except (SQLAlchemyError, psycopg.Error, ValueError):
                # Never log connection strings or driver errors containing credentials.
                logger.warning("dependency_unavailable", extra={"dependency": "postgresql"})
                return JSONResponse(
                    status_code=503,
                    content={"status": "not_ready", "dependencies": {"postgresql": "unavailable"}},
                )
        return {"status": "ready"}

    @application.get("/version")
    def version():
        return {"app_version": settings.app_version, "git_sha": settings.git_sha}

    @application.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(registry), headers={"Content-Type": CONTENT_TYPE_LATEST})

    return application


app = create_app()
