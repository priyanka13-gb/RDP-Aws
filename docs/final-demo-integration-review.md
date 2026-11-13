# Final demo integration review — Task 31

Reviewed 14 November 2026 IST (some evidence timestamps are 13 November UTC).
No deployment, live failure, image push, Git push or remote state write occurred.

## Integration assessment

Task 27's historical deployment/teardown audit is retained with its evidence
limits: successful verifier summaries and AWS history corroborate the first
demo, but raw HTTP/task/target/log transcripts were not retained. It does not
prove a current deployment or a completed rollback drill.

Task 28 CI is present at `.github/workflows/ci.yml`, originally committed in
`d25a95c`. Local evidence is not a hosted CI pass. Public GitHub API requests for
CI runs/environment returned 404, and the repository variable returned 401.
Without authenticated access, missing/private resources cannot be distinguished.
No passing hosted run is verified. The reviewed Actionlint check disables its
optional ShellCheck/Pyflakes integrations; Ruff is checked separately.

Task 29 adds a manual-only release workflow, with publishing false by default.
The reusable CI gate has contents:read only. Only the protected publishing job
requests id-token:write after the successful gate. It builds/scans/smoke-tests the
actual publishing image before obtaining credentials, requires exact source and
recipe hashes, refuses existing immutable tags, and checks root/AMD64/config
digests and ECR scan results. Only sanitized reports are uploaded. There are no
ECS, ALB, Terraform or repository-creation permissions in its proposed IAM policy.

IAM templates require exact audience sts.amazonaws.com and an exact confirmed
repository/environment subject, not a wildcard. The actual subject and GitHub
environment reviewers/main-only deployment rules must be verified before
provisioning. See [GitHub's OIDC guidance](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).
The proposed role `rdp-github-ecr-release` is currently absent (NoSuchEntity).
No live OIDC exchange, environment approval, hosted release or ECR push was tested.
Publishing is **NO-GO** until separately approved setup and hosted validation.
The local default-disabled guard does not establish the remote variable's value.

Task 30 monitoring and local failure scenarios passed again. A current completed
healthy ECS deployment does not exist. Live rollback remains **NOT VERIFIED**.
There are no current demo ECS/ALB/VPC resources within the existing status scope;
empty remote dev state remains normal. ECR image and S3 state storage remain.
Status is scoped inventory, not an account-wide billing or orphan-resource audit.

## Gates and costs

Fresh results are recorded in [Task 31 evidence](../evidence/task31/validation.json).
All 93 unit tests, two PostgreSQL integration tests and five local failure
scenarios passed. Ruff, Terraform formatting, nine isolated Terraform
configurations and 23 mock tests passed. A fresh Trivy scan of the existing
Task 29 local image found zero vulnerabilities across 38 OS and 19 Python
packages. Its archive checksum matches the original build record; it is not a
new release built from the final review commit. The initial scan attempt used
the wrong archive path; the corrected attempt completed successfully.
Python tests use Linux Python 3.12 and disposable PostgreSQL16 containers; existing
database volumes are preserved. Terraform checks use isolated backend-disabled
copies, never the real S3 backend. No runtime, Docker, Terraform architecture or
credential changes are required by this review.

No AWS resource was created, so this review adds no standing infrastructure cost.
Read-only API calls can have request charges. Existing ECR/S3 storage continues.
The project's prior estimate is roughly $0.055/hour baseline or $0.066/hour for
the quieter all-in example, before credits/tax: approximately $0.11–$0.13 for two
hours. These are planning estimates, not a new pricing quote or cost cap. ALB,
Fargate, public IPv4, CloudWatch, storage and traffic vary; rollback overlap can
temporarily double task capacity. Credits/expiry and current prices must be
checked before approval. No NAT, RDS, paid alarm or service is added by this work.

## Short supervised live-demo checklist — commands NOT EXECUTED

1. Resolve the hosted-CI evidence gap: after a separately authorized Git push,
   verify every CI job passes for the intended commit. Keep ECR publishing
   disabled; this demo uses the already approved image, not a new release.
2. Confirm clean Git, AWS profile rdp-dev, Sydney backend, sufficient permissions
   (including PassRole and first-use service-linked roles), quotas, credits,
   approval window and a named operator who can perform teardown. Test status
   access and prepare a second authenticated terminal. Do not alter credentials.
3. Set an independent alarm for a maximum two-hour demo. Reserve the final
   30 minutes for cleanup. No automated timer guarantees AWS deletion; outages,
   credential expiry or permission failures can prevent cleanup. Obtain explicit
   deployment AND teardown authorization before starting. Without an available
   cleanup operator and contingency, do not deploy.
4. Prepare a fresh plan after the final clean source commit:

   ```powershell
   git status --short
   .venv/Scripts/python.exe scripts/demo.py status
   .venv/Scripts/python.exe scripts/demo.py prepare
   ```

   Review 34 creates, zero updates/deletes/replacements, approved AMD64 digest,
   ALB-only task ingress, no NAT/RDS, account/region/backend, checksum and one-hour
   expiry. Stop on any unexpected difference. This review did not generate or
   approve a fresh saved deployment plan.
5. Only after separate approval, execute the reviewed deployment workflow:

   ```powershell
   ./scripts/deploy-demo.ps1
   ./scripts/verify-demo.ps1
   ./scripts/monitor-demo.ps1
   .venv/Scripts/python.exe scripts/monitor_demo.py --require-rollback-baseline
   ```

   Confirm current PRIMARY COMPLETED, approved digest, one healthy task, healthy
   ALB targets, `/health`, `/ready`, `/version`, `/metrics`, and log delivery.
   Public HTTP only: send no sensitive information. Preserve sanitized endpoint
   results and task/target/rollout summaries before teardown, filling Task 27's
   evidence gaps. Monitor every few minutes and after any abnormal response.
6. Do not inject a failure for the normal demo. Rollback is an optional separate
   approval under [the Task 30 runbook](monitoring-failure-recovery.md). First
   establish the completed healthy baseline. Capture the failed deployment and
   restored baseline before claiming automatic rollback. Manual restoration is
   not proof of automatic rollback. Stop within the approved failure window and
   retain enough time for cleanup.
7. For any failure or interruption: preserve state and evidence; run read-only
   status/monitor. Do not retry a consumed plan, force-unlock an active operation,
   weaken security groups, or delete resources manually. Use the reviewed partial
   apply/cleanup procedure; unexpected replacement or unrelated resources require
   a separate recovery review.
8. At the alarm, after any failed demo, or immediately after the presentation,
   execute the separately approved, confirmation-protected teardown:

   ```powershell
   ./scripts/cleanup-demo.ps1
   ./scripts/status-demo.ps1
   .venv/Scripts/python.exe scripts/demo.py monitor
   ```

   Cleanup generates a fresh dev-only delete plan and prompts; it preserves ECR
   and bootstrap. Verify zero tasks/services/clusters, ALB, VPC/ENIs/public IPs,
   log groups and state resources. If cleanup fails, keep the incident open,
   restore authorized operator access and retry only a newly reviewed cleanup
   plan. Escalate to the account owner; never report teardown complete from a
   command attempt alone. Check Billing/credits again after delayed usage settles.

**Recommendation: NO-GO for live deployment today.** Local verification can be
committed safely, but hosted CI evidence, a fresh reviewed post-commit deployment
plan, current budget confirmation and separate deployment/teardown approval remain
prerequisites. OIDC provisioning is a release-workflow blocker, not a requirement
for the human-supervised demo using the existing image.
