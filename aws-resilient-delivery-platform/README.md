# AWS Resilient Delivery Platform

FastAPI service with health and dependency readiness probes, JSON application logs,
and Prometheus request metrics. Infrastructure and workflow directories remain scaffolds.

## Local setup

Use Python 3.12 or newer. From this repository directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

If activation is disabled, run `.\.venv\Scripts\python.exe` in place of `python`.
On Linux/macOS, activate with `source .venv/bin/activate`.
Dependencies are installed only in the virtual environment. `--no-access-log`
disables Uvicorn's duplicate plain-text request logs; application request logs are JSON.
Uvicorn startup/shutdown messages retain Uvicorn's default format.

## Endpoints

| Endpoint | Response |
| --- | --- |
| `GET /` | Project name and environment |
| `GET /health` | 200, `{"status":"healthy"}`; independent of PostgreSQL |
| `GET /ready` | 200, `{"status":"ready"}`, or 503 if configured PostgreSQL is unavailable |
| `GET /version` | `app_version` and `git_sha` |
| `GET /metrics` | Prometheus text exposition, without a trailing-slash redirect |

Interactive API documentation is available at `/docs`.

## Configuration

Environment variables are read when the application is created. Restart after changes.
The application does not automatically load `.env` files.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_VERSION` | `0.1.0` | Release version |
| `GIT_SHA` | `unknown` | Source revision |
| `APP_ENV` | `development` | Environment label |
| `LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR, or CRITICAL |
| `DATABASE_URL` | unset | PostgreSQL connection string; enables readiness checking when nonempty |
| `DATABASE_TIMEOUT_SECONDS` | `3` | Connection and statement timeout, integer from 2 to 30 |

Example without a database:

```powershell
$env:APP_VERSION = '0.1.0'
$env:GIT_SHA = git rev-parse HEAD
python -m uvicorn app.main:app --no-access-log
```

Supply `DATABASE_URL` through your environment or secret-management system. Never
commit credentials. Each configured readiness probe opens a connection, runs
`SELECT 1`, and closes it. Connection and query timeouts are separate limits,
not a single end-to-end deadline; multi-host connection strings can take longer.
No database tables, schemas, or AWS resources are created. Driver error details
and connection strings are excluded from readiness responses and application logs.

## Observability

`http_requests_total` records method, route template, and HTTP status.
`http_request_duration_seconds` records request latency by method and route template.
Unknown paths share the `unmatched` label to avoid unbounded metric cardinality.
Request logs include UTC timestamp, level, method, route, status, and duration;
they omit query strings and request bodies. Latency measures processing until the
response is returned by the handler, not client download time.

Metrics use a registry per application instance. Run a single Uvicorn worker for
this implementation; multiple workers require Prometheus multiprocess configuration.
A metrics scrape records its own request after generating that scrape's response.

## Tests and lint

```powershell
python -m pytest -v
python -m ruff check .
```

Tests cover every endpoint, environment configuration, successful and failed database
probes, connection cleanup, metrics values, bounded route labels, and JSON formatting.
Database tests use mocks and require no running PostgreSQL server or AWS account.
Live PostgreSQL connectivity must be verified separately in the target environment.
