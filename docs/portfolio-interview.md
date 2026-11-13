# Interview brief and resume bullets

## 60-second introduction

I built a FastAPI delivery platform with health/readiness probes, structured logs
and Prometheus metrics. Local development uses Docker and PostgreSQL16. The
runtime is a digest-pinned Python3.12 Alpine image running as a non-root user.
Terraform separates bootstrap, image registry and application state and defines
a short-lived Fargate service behind an ALB. GitHub CI runs Python/PostgreSQL
tests, Terraform validation/mock plans, a Docker build and vulnerability gating.
I audited a real deployment and teardown, then kept the demo absent to control
cost. OIDC publishing is deliberately deferred within the Free-plan boundary;
manual releases use temporary CLI credentials. Local failure scenarios are
tested, while live AWS rollback is explicitly unverified.

## Evidence-first five-minute walkthrough

1. Show README endpoint/configuration tables and app/main.py: liveness remains
   independent of optional database readiness; connection details are not logged.
2. Show app/Dockerfile, non-root UID and the dated scan evidence. Explain that a
   pinned base alone does not freeze moving package repositories/dependencies.
3. Open [successful hosted CI](https://github.com/priyanka13-gb/RDP-Aws/actions/runs/43487727943).
   Identify 93 unit tests, two PostgreSQL tests, 23 mock tests and zero scan findings.
4. Show network/ECS modules: ALB-to-task ingress only, /ready target checks,
   X86_64, CloudWatch retention and no NAT/RDS in the initial cost_saver demo.
5. Show [the audited deployment/teardown](first-deployment-teardown-audit.md)
   and [local recovery timeline](incidents/local-failure-drill.md). Explain their
   different evidence limits. Do not redeploy solely to make an interview claim.

If running the app locally, use the existing Compose setup without deleting its
volume. Stop after the walkthrough; do not push an image or run cloud deployment
commands in an interview without explicit authorization and a cleanup operator.

## Resume bullets — measured, defensible claims

- Built a FastAPI service with PostgreSQL16 readiness checks, pooled connections,
  structured JSON logging and Prometheus request/latency metrics.
- Implemented SHA-pinned GitHub Actions CI covering 93 unit tests, two PostgreSQL
  integration tests, nine Terraform validations and 23 mock-plan tests, with an
  AMD64 Docker build and HIGH/CRITICAL vulnerability gate.
- Containerized Python3.12 on a digest-pinned Alpine runtime with non-root UID10001;
  verified zero Trivy findings at the recorded scan date and published an immutable
  Git-tagged ECR image with platform-digest verification.
- Developed Terraform modules for a cost-conscious ECS Fargate/ALB demonstration
  with separate remote states, ALB-restricted task ingress and CloudWatch logging;
  audited a 34-resource deployment and subsequent teardown.
- Added read-only ECS/ALB monitoring and five local Docker failure/recovery scenarios,
  with explicit deployment approvals, plan-expiry safeguards and cost-aware cleanup.

Use the bullets only for work you can personally explain. Do not describe the
project as enabled OIDC CD, production-ready, highly available under measured
load, zero-cost, or automatically rolled back in AWS. Those claims are unverified.

## Tradeoffs to explain

| Interview question | Accurate answer |
| --- | --- |
| Why no OIDC release now? | IAM provider inspection is denied in this Free-plan project; explicit IdP management is an advanced-feature boundary. I retained the design without upgrading or weakening trust. |
| Why public task IPs? | Initial cost_saver avoids NAT; task ingress remains restricted to the ALB. Production egress/TLS/availability need a separate design and budget. |
| Is rollback proven? | Circuit breaker is configured; five local failures/recoveries passed. Live ECS rollback is NOT VERIFIED. |
| Did cloud deployment happen? | The historical audit corroborates deployment and teardown; raw endpoint/log archives are incomplete. Current demo inventory is empty. |
| Is the image always secure? | No. Scans are dated observations; every future release needs a fresh scan and review. |
| Is teardown guaranteed? | No. It is confirmation-protected and verified, but needs a functioning operator session and AWS availability. |

See [portfolio status](portfolio-status.md) for current limits and remaining work.
