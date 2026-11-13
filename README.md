# AWS Resilient Delivery Platform

FastAPI service with health and dependency readiness probes, JSON application logs,
and Prometheus request metrics. Docker/PostgreSQL16 support local development;
Terraform defines an on-demand ALB/ECS Fargate demo, with separate S3 bootstrap,
ECR and dev state ownership. A first AWS demo and teardown were audited; the dev
stack is kept absent between separately approved demonstrations.

## Verified portfolio status — 14 November 2026

- GitHub-hosted [CI run 43487727943](https://github.com/priyanka13-gb/RDP-Aws/actions/runs/43487727943)
  passed for commit `693efb2fd5f83c1ce60a6a029bd6f65223765d70`: 93 unit tests,
  two PostgreSQL16 integration tests, 23 Terraform mock tests, Ruff, an AMD64
  Docker build and a Trivy scan with zero findings at scan time.
- Production Dockerfile uses digest-pinned Python3.12/Alpine, Linux AMD64,
  UID/GID10001 and a runtime without pip. Scans are dated evidence, not a
  guarantee that future vulnerability databases will remain clean.
- ECR release `git-9b18a3109aa2` was published and verified previously.
  [The first live deployment/teardown audit](docs/first-deployment-teardown-audit.md)
  records a 34-resource ECS/ALB demonstration and its evidence limitations.
- Five local Docker failure/recovery scenarios passed. ECS circuit-breaker
  rollback is configured; **live AWS rollback is NOT VERIFIED**.
- GitHub OIDC publishing is **disabled and deferred**. The account remains on
  the Free plan; IAM provider reads are denied. No advanced features or plan
  upgrade are needed to present this portfolio. Releases remain an explicitly
  approved manual operation using temporary AWS CLI credentials.

Start with the [interview brief and resume bullets](docs/portfolio-interview.md),
[temporary-credential ECR procedure](docs/manual-ecr-temporary-credentials.md),
and [account limitations/remaining work](docs/portfolio-status.md).
Task34 is a local documentation commit only; the hosted run above does not
represent a hosted run of that later documentation commit. No new image or
deployment is produced by finalizing the portfolio.

## Local setup

Use Python 3.12, the tested runtime. From this repository directory in PowerShell:

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
| `DATABASE_PASSWORD_FILE` | unset | UTF-8 password secret file; overrides a password in DATABASE_URL |
| `DATABASE_TIMEOUT_SECONDS` | `3` | Connection and statement timeout, integer from 2 to 30 |

Example without a database:

```powershell
$env:APP_VERSION = '0.1.0'
$env:GIT_SHA = git rev-parse HEAD
python -m uvicorn app.main:app --no-access-log
```

Supply `DATABASE_URL` through your environment or secret-management system. Never
commit credentials. Each configured readiness probe borrows a SQLAlchemy/psycopg
connection, runs `SELECT 1`, and returns it to the pool. The pool allows five
connections with no overflow, pre-pings reused connections, and recycles them after
300 seconds. Pool checkout, connection, and query timeouts are separate limits,
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
Unit database tests use mocks and require no running PostgreSQL server or AWS
account. Real PostgreSQL service/Compose integration tests are opt-in; CI runs
the PostgreSQL16 service tests separately.

## Docker architecture and requirements

Install Docker Engine with Compose v2 or newer, or Docker Desktop with its Linux
engine running. Windows Docker Desktop requires its supported WSL2/virtualization
setup. Python 3.12+ is needed locally only for the setup script and host-side tests.

The multi-stage `app/Dockerfile` installs compatible Python dependencies on a
digest-pinned Python3.12 Alpine builder and copies them to the matching runtime.
The final runtime removes pip. Uvicorn runs as UID/GID 10001 on
`0.0.0.0:8000`. The build context is this repository root; `.dockerignore` allows
only application source and packaging inputs, excluding secrets, caches, and Git.

Compose publishes the app at `127.0.0.1:8000`. The app also joins an internal backend
network to reach `db:5432`. PostgreSQL uses the official `postgres:16` image and
has no published host port. Its data lives in the `postgres_data` named volume.
The app waits for PostgreSQL's `pg_isready` check; its own health check calls `/ready`.
`/health` remains independent of the database.

## Run Docker Compose

From the repository root:

```powershell
python scripts/init_local_secrets.py
docker compose config
docker compose build
docker compose up -d --wait
docker compose ps
```

The script generates a random password in ignored `.secrets/db_password.txt` and
preserves any existing file. Both services receive it through a read-only Compose
secret at `/run/secrets/db_password`; the password is absent from Compose environment
values and image layers. Keep this local file private and do not commit or share it.
Local Compose secrets are mounted files, not an encrypted secret store.
PostgreSQL creates database `resilient_db` and user `resilient_user` on first startup.
The official image's initial user is an administrator; this is a local development
setup, and a deployment should provision a separate least-privilege application role.

Optional nonsecret `APP_VERSION`, `GIT_SHA`, `APP_ENV`, and `LOG_LEVEL` overrides can
be set in the shell or an ignored root `.env`. `DATABASE_URL` in Compose uses `db`,
while a host-run application needs a separately reachable PostgreSQL server.

## Check health and connectivity

```powershell
docker compose ps
docker compose logs --tail 100 app db
curl.exe --fail http://127.0.0.1:8000/health
curl.exe --fail http://127.0.0.1:8000/ready
curl.exe --fail http://127.0.0.1:8000/version
curl.exe --fail http://127.0.0.1:8000/metrics
docker compose exec db pg_isready -U resilient_user -d resilient_db
docker compose exec db psql -U resilient_user -d resilient_db -c 'SELECT 1;'
```

Use `curl` instead of `curl.exe` on Linux/macOS. The psql command verifies the
database locally; `/ready` additionally checks the app's authenticated network connection.

Run unit tests and lint in the local virtual environment:

```powershell
python -m pytest -v
python -m ruff check .
```

After Compose is healthy, enable the actual PostgreSQL 16 integration tests:

```powershell
$env:RUN_DOCKER_INTEGRATION = '1'
python -m pytest -v -m integration
Remove-Item Env:RUN_DOCKER_INTEGRATION
```

On Linux/macOS use `RUN_DOCKER_INTEGRATION=1 python -m pytest -v -m integration`.
The tests run a query through SQLAlchemy inside the app container, check the server
version/database name, and call the HTTP endpoints. They require the existing
Compose stack and never create or delete volumes. Default test runs skip them.

## Restart and stop safely

```powershell
docker compose restart
docker compose up -d --build --wait
docker compose stop
docker compose start
docker compose down
```

Use `up -d --build --wait` after code or configuration changes; `restart` does not
apply changed configuration. `stop` preserves containers and data; `down` removes
containers and networks while retaining the named database volume. Do not use
`down -v` or volume-pruning commands if you need to preserve the database.

## Troubleshooting

- Missing Docker daemon pipe or socket: start Docker Desktop's Linux engine, then
  check `docker version`, `docker context show`, and `docker info`.
- Missing secret file: run `python scripts/init_local_secrets.py` before startup.
- Port 8000 already occupied: stop the conflicting local service or intentionally
  change only the app's localhost port mapping.
- App unhealthy: inspect `docker compose logs --tail 100 app db`, then check `/ready`.
  Database outages return 503 while `/health` stays 200. Pool/query/connection
  timeouts are separate, so a failed probe can exceed three seconds in total.
- Authentication failures after changing the secret: PostgreSQL initialization
  variables only apply to an empty data directory. Restore the matching secret or
  rotate the database password deliberately; do not delete the volume to fix this.
- Build failures: inspect `docker compose build --progress plain` output and verify
  access to Docker Hub and PyPI. Dependency ranges are currently resolved at build
  time; a release lockfile/image digest workflow is outside this phase.

Reference: [Docker Compose secrets](https://docs.docker.com/compose/how-tos/use-secrets)
and [startup ordering](https://docs.docker.com/compose/how-tos/startup-order).

## Terraform networking foundation

See [network architecture, file guide, validation and cost tradeoffs](docs/networking.md).
The dev configuration targets Sydney (`ap-southeast-2`) with VPC `10.0.0.0/16`, two
public and two private subnets, and security groups for a future ALB, ECS tasks,
and PostgreSQL. Default `cost_saver` mode creates no NAT gateways or Elastic IPs.
`production_like` requires an explicit billable `single` or `per_az` NAT choice.

```powershell
terraform fmt -recursive -check
python scripts/ci_terraform.py
```

These are local validation commands, not a deployment. No apply/destroy is part of
this milestone. The existing Docker/PostgreSQL workflow is independent of Terraform.

## ECS Fargate infrastructure (normally stopped and removed)

See the [ECS architecture, file guide, security and deployment prerequisites](docs/ecs-infrastructure.md)
and [state bootstrap procedure](infra/bootstrap/README.md).

The current dev demo uses **HTTP port 80** on the ALB, public-subnet Fargate tasks
with public IPs in cost_saver, and ALB-only ingress to task port 8000. It creates
no NAT by default. Private production_like tasks require an explicit NAT choice.
Database settings are empty in ECS; local Docker/PostgreSQL behavior is unchanged.
HTTP must carry only non-sensitive demo traffic. RDS is deferred.

Dev requires an actual release image URI in its ECR repository before deployment.
The S3 backend has been initialized with native locking. Bootstrap and ECR are
retained; the dev application stack has been removed. Do not reinitialize,
reconfigure or migrate state for portfolio verification. For isolated local checks:

```powershell
python scripts/ci_terraform.py
```

These tests use mocked plans and do not deploy resources. No image push, credential
creation, real apply/destroy, or state migration is part of this implementation.

## AWS deployment readiness

See the [read-only readiness results](evidence/aws-deployment-readiness.md),
[first deployment procedure](docs/first-aws-deployment.md), and separate
[teardown and cost-audit procedure](docs/teardown-cost-audit.md).
Deployment and image upload still require authorization; these checks deploy nothing.

The [S3 bootstrap deployment review](docs/bootstrap-deployment-review.md) records the
proposed bucket, exact dev state key, read-only existence checks, and commands for a
future approved first apply; it is the historical pre-creation review.
The bucket and initialized backend now exist. The
[Task 11 dev backend review](docs/dev-backend-initialization-review.md) is historical
preparation evidence, not an instruction to repeat initialization.

The subsequent [Task 12 ECR deployment plan](docs/ecr-deployment-plan.md) records the
now-initialized backend metadata, proposed ECR-only bootstrap, image commands and
remaining verification blockers. No ECR repository or image was created by that review.

The [Task 13 deployment verification](docs/task13-deployment-status.md) describes
an earlier point in time. It is superseded by the existing ECR release and
[first deployment/teardown audit](docs/first-deployment-teardown-audit.md).
Use [portfolio status](docs/portfolio-status.md) for current limitations and evidence.

## Isolated ECR deployment root

[infra/envs/ecr](infra/envs/ecr/README.md) now owns ECR under a dedicated S3 state key.
Dev reads the repository through an AWS data source and no longer creates it.
Deploy ECR and publish an approved image before planning dev. This supersedes the
older targeted-dev ECR bootstrap instructions; no state migration is required for
the currently empty dev state.


## On-demand interview demo

Keep the dev AWS stack absent between interviews. The reviewed PowerShell workflow
prepares a plan, requires typed confirmation to deploy or clean up, and verifies AWS
resources after teardown. Bootstrap S3 state and the existing ECR image are retained.

```powershell
.\scripts\status-demo.ps1
.\scripts\prepare-demo.ps1
.\scripts\deploy-demo.ps1
.\scripts\verify-demo.ps1
.\scripts\cleanup-demo.ps1
.\scripts\status-demo.ps1
```

Review and commit source before preparation/deployment. No deployment is authorized
by installing these scripts. See [the interview demo guide](docs/interview-demo-guide.md)
for costs, execution-policy alternatives, safety checks, budget guidance, failure
recovery, and five/fifteen-minute interview sequences.


## Continuous integration

Pull requests and main pushes run credential-free Python/Ruff tests, PostgreSQL16
service integration tests, isolated Terraform validation/mock tests, and an AMD64
Docker build with a HIGH/CRITICAL vulnerability gate. No AWS deployment occurs.
See [CI design, security policy and publishing commands](docs/github-actions-ci.md).
The four CI jobs are configured as required GitHub Actions checks on main.
PR approval count remains zero; environment reviewer protection is incomplete.
The dormant OIDC workflow is not a completed CD implementation. Keep its
publishing enablement variable absent/false; do not install the authentication
template or provision IAM merely to complete the portfolio.
