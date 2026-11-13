# GitHub Actions CI

`.github/workflows/ci.yml` runs on pull requests and pushes to main. It performs
checks only: no AWS login/OIDC token, Terraform remote plan/apply/destroy, deployment,
ECR authentication or image push. Token permissions are `contents: read`; checkout
credentials are not persisted. There is no pull_request_target trigger. Concurrent
runs for the same ref are cancelled; jobs have explicit timeouts.

## Jobs and boundaries

1. **Python:** Ubuntu24.04 + supported Python3.12, pip download cache keyed to
   pyproject.toml, install .[dev], Ruff and all non-integration tests. This includes
   the demo workflow refusal tests; no actual demo operation runs.
2. **PostgreSQL:** official digest-pinned PostgreSQL16 service, port bound to
   runner loopback, pg_isready health check and two real service tests. A disposable
   run-specific test password is generated from run identity; it is intentionally
   not a production secret or reused outside CI. Tests exercise SQL/pool return,
   readiness, liveness, version/metrics and a real unreachable-database scenario.
   Existing Docker Compose integration tests are retained for local validation.
3. **Terraform:** CLI1.17.1, recursive fmt, backend-disabled init and validate of
   all nine implemented roots/modules; all four existing mock-test suites (23 runs).
   The helper copies only HCL to a fresh ignored sandbox and TF_DATA_DIR, clears AWS
   credential/profile variables and uses empty AWS config/credential paths with
   metadata discovery disabled. Backend files/state are not copied or initialized.
   Existing tracked AWS6.71.0 lock files are reused; modules without locks receive
   the dev lock in the temporary copy only. A local provider cache avoids repeated
   downloads in a job; no provider/state directory is uploaded or shared across jobs.
4. **Image:** repository-context Docker build for linux/amd64; platform and UID10001
   checked. A pinned official Aqua Trivy image scans the exported local image with
   current database data. Nothing is pushed. No production Dockerfile change.

The implementation preserves all existing infrastructure, application, Compose
behavior and the on-demand deployment workflow. CI service tests are opt-in via
RUN_POSTGRES_INTEGRATION=1; local Docker tests still use RUN_DOCKER_INTEGRATION=1.
Do not enable the service tests against a production database.

## Security scan policy and reports

All scan severities and unfixed findings remain in the normalized report. Collection
uses Trivy exit-code0 so the full report can be sanitized; this is **not the gate**.
The subsequent checked-in reporter returns exit1 for **any HIGH or CRITICAL**, with
or without available fixes. Scanner execution errors fail the job independently.
Malformed reports or missing OS/Python package inventories also fail closed.
There is no ignore-unfixed switch, CVE allowlist, continue-on-error or severity
suppression. LOW/MEDIUM/UNKNOWN findings remain visible but do not fail this policy.
The pipeline does not claim PostgreSQL service, GitHub runner OS or Terraform cloud
resources were scanned as production artifacts; Trivy targets the application image.

Artifacts are allowlisted JSON summaries retained for seven days: test totals,
Terraform stage/test counts, complete normalized vulnerability rows and inventory
counts. They exclude raw tracebacks, log bodies, environment, registry metadata,
Terraform state/plans, .env, local authentication config, Docker archives and build
contexts. `include-hidden-files: true` is used only for each **explicit report file**
inside .tools; no broad hidden directory is uploaded. Raw reports stay in ignored
.tools/ci/raw for the duration of the ephemeral job and are never uploaded.
A failed step stays failed even if its summary upload succeeds.

All external Actions use full immutable commit SHAs. Their official release tags,
resolved commit IDs and metadata source links are in [ci-action-pins.json](ci-action-pins.json).
Review checked release identity, action inputs and Node24 runtime compatibility;
this was not an independent audit of every bundled JavaScript dependency.
GitHub-hosted Ubuntu runners support that runtime. Trivy and PostgreSQL are pinned
by immutable image digests; maintainers must periodically review updated versions.
Base pinning does not lock Python dependency ranges or apk repositories: fresh
builds/scans may expose a new issue and correctly fail.

## Local reproduction

```powershell
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m pytest -m 'not integration'
terraform fmt -check -recursive
.venv/Scripts/python.exe scripts/ci_terraform.py
docker build --platform linux/amd64 -f app/Dockerfile -t rdp-ci:local .
```

Use the existing Linux environment if Windows Application Control blocks a native
Python DLL; do not disable OS policy. To run new service tests locally, use an
isolated PostgreSQL16 instance, set RUN_POSTGRES_INTEGRATION=1 and DATABASE_URL
privately, then run `python -m pytest tests/test_postgres_integration.py`. No cloud
credential is needed. Service tests do not validate production/RDS TLS.

The CI helper never runs init against the developer's existing .terraform directory.
It may contact only public provider/distribution registries during installation;
mock tests do not require or use live AWS authentication. Terraform fmt is read-only.
Raw private logs are retained locally under .tools/ci/raw when debugging.

## Publish and observe - commands only

No Git push or hosted CI run was performed during implementation. From the verified
CI commit, publish a branch and open a pull request:

```powershell
git push origin HEAD:ci/github-actions
gh pr create --base main --head ci/github-actions --title "Add credential-free CI" --body "Run Python, PostgreSQL, Terraform mock checks and an AMD64 image vulnerability gate without AWS access."
gh run list --workflow ci.yml --branch ci/github-actions --event pull_request
gh run watch <RUN_ID> --exit-status
gh run view <RUN_ID> --log-failed
gh run download <RUN_ID> --dir .tools/hosted-ci-reports
```

Replace RUN_ID with the numeric run ID, without angle brackets in the shell.
The workflow triggers from opening/updating a PR, not pushing an arbitrary branch
alone. Merge only after all four jobs pass; main pushes run it again. Consider branch
protection requiring these checks after the first hosted run. No repository settings
were changed automatically. Fork PRs may require GitHub approval under repository
policy. There is no workflow_dispatch trigger in this implementation.

GitHub-hosted runner minutes and artifact storage can consume GitHub plan allowances
for private repositories. Seven-day summary-only retention and timeouts limit usage,
but they are not a billing cap. No additional AWS infrastructure or paid AWS monitoring
was introduced. Public-repository runner terms and current account limits should be
checked before sustained use. Local validation cannot prove GitHub orchestration,
runner image compatibility or permissions until the first authorized hosted run.
