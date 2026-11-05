# ECS infrastructure verification — 2026-11-05

## Scope and tools

Implementation only; no AWS deployment. Repository layout and working application,
Docker/PostgreSQL components were preserved. Terraform **1.17.1** on Windows AMD64;
AWS provider **6.71.0** from the existing committed lockfile.

## Actual command results

| Command/check | Result |
| --- | --- |
| `terraform fmt -recursive` | Formatted new/updated Terraform and mock tests |
| `terraform fmt -check -recursive` | Passed, exit 0 |
| Dev `init -backend=false -input=false -lockfile=readonly` | Successfully initialized all six modules and test module references |
| Dev `validate` | Success: configuration is valid |
| Dev `test` | **15 passed, 0 failed**, exit 0 |
| Bootstrap `init -backend=false -input=false -lockfile=readonly` with local provider directory | Successfully initialized |
| Bootstrap `validate` | Success: configuration is valid |
| Bootstrap `test` | **1 passed, 0 failed**, exit 0 |
| Network module `init -backend=false -input=false -lockfile=readonly` with local provider directory | Successfully initialized |
| Network module `validate` | Success: configuration is valid |
| Network module `test` | **5 passed, 0 failed**, exit 0 |
| `git diff --check` | Passed; only existing Git CRLF-conversion notices |
| Diff of app, compose.yaml, pyproject.toml, .dockerignore, Python tests and scripts | Empty; those files are unchanged |
| Git ignore checks for bootstrap state, state backup and local dev backend.hcl | All ignored |

Total: **21 mock-plan tests passed**. Tests use a mock AWS provider and every run
explicitly sets `command = plan`. No test uses real apply/destroy or AWS credentials.

The first dev init was blocked by sandbox network restrictions; the rerun with
required access succeeded. Bootstrap provider copying also required access outside
the sandbox. Bootstrap reused the dev provider through `-plugin-dir` and its existing
release-checksum lockfile; Terraform labels local-directory installs unauthenticated
because it does not re-fetch the signing material during that copy.

One initial mock security-group test had unknown IDs during plan. Adding explicit
`override_during=plan` to its resource overrides fixed the fixture. All assertions
passed on rerun. Image-input checks were tightened to reject `latest` and malformed
SHA256 digests; both additional negative tests passed.

## Coverage

- Dev graph integration and safe defaults; rejection of RDS enablement and unapproved SSM use.
- Public task subnets/public IPs in cost_saver; private task subnets/no public IPs in production_like.
- ECS task CPU/memory/Linux platform, UID, port, image CMD preservation, liveness and logging.
- Empty database settings and rejection of database injection through SSM.
- ALB HTTP listener, two public subnets, IP target group, port 8000 and readiness thresholds.
- ALB-only ECS ingress and ECS-only PostgreSQL ingress; no NAT/EIPs in cost_saver.
- Scoped execution-role ECR/log permissions, separate roles, ECS/account trust, optional SSM/KMS scope.
- Immutable/scanned/encrypted ECR, image retention, and seven-day log retention.
- Circuit-breaker rollback, health grace and desired count.
- S3 public-access block, versioning, encryption, force-destroy protection and HTTPS-only policy.
- Existing network per-AZ/single NAT behavior and rejection of contradictory NAT settings.

## Files created

- `infra/bootstrap/`: `versions.tf`, `variables.tf`, `main.tf`, `outputs.tf`,
  `terraform.tfvars.example`, `.terraform.lock.hcl`, `README.md`, `tests/state.tftest.hcl`.
- `infra/modules/ecr/`, `infra/modules/observability/`, `infra/modules/iam/`,
  `infra/modules/alb/`, `infra/modules/ecs_service/`: each has `versions.tf`,
  `variables.tf`, `main.tf`, and `outputs.tf`.
- `infra/envs/dev/backend.hcl.example` and `tests/ecs.tftest.hcl`,
  `tests/modules.tftest.hcl`, `tests/wiring.tftest.hcl` under the dev root.
- `docs/ecs-infrastructure.md` and this verification report.

## Files modified

- `.gitignore`, `README.md`, `docs/networking.md`.
- `infra/envs/dev/`: `main.tf`, `outputs.tf`, `providers.tf`, `variables.tf`,
  `versions.tf`, `terraform.tfvars.example`.
- `infra/modules/network/variables.tf` and `security_groups.tf`: parameterized
  ALB ingress port while retaining the existing rule address and CIDR allocations.

## Remaining boundaries

No AWS resources, credentials, container-image pushes, ECS deployments, backend
connections, state migrations, real Terraform apply/destroy commands, or Git pushes
were performed. No deployment state files were produced in bootstrap or dev.

The existing Dockerfile and FastAPI endpoints were inspected and matched by the
task definition, but the image was not built, pulled or run in ECS during this task.
Python tests were not rerun because Python/application files were not changed.

Mock tests verify configuration logic, not AWS permission execution, account/AZ
availability, quotas, image existence, end-to-end network access, actual ALB health,
SSM retrieval or real rollback. Those require a separately authorized deployment.
HTTP demo traffic, single-task availability and public task IP tradeoffs are detailed
in `docs/ecs-infrastructure.md`. No unresolved local validation/test failures remain.
