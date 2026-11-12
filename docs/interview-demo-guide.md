# Interview demo: deploy briefly, verify, remove

This portfolio retains FastAPI, Docker, PostgreSQL locally and VPC/ALB/ECS/IAM/
CloudWatch on AWS. AWS demos run without PostgreSQL/RDS, NAT gateways or extra
paid monitoring. Bootstrap S3 state and the existing immutable ECR image remain
between demos; the dev application infrastructure should normally be absent.

## Start here: Windows PowerShell

Run from the repository root with its existing `.venv`, Terraform, AWS CLI and
initialized dev S3 backend. Profile `rdp-dev`, region `ap-southeast-2`, workspace
`default` and the existing bucket/dev key are enforced. Scripts never initialize,
migrate or reconfigure the backend or change credentials. Do not launch two
Terraform operators concurrently. Review/commit these new files locally before
prepare/deploy; those commands refuse dirty Git. No automatic commit is provided.

```powershell
.\scripts\status-demo.ps1
.\scripts\prepare-demo.ps1
# Read every resource/action and checksum. Stops without applying.
.\scripts\deploy-demo.ps1
# Requires: DEPLOY dev <first 12 characters of displayed plan checksum>
.\scripts\verify-demo.ps1
# After the demonstration:
.\scripts\cleanup-demo.ps1
# Displays fresh destroy plan; requires: DESTROY dev <checksum prefix>
.\scripts\status-demo.ps1
```

PowerShell 5.1 and 7 compatible wrappers use the repository Python interpreter;
all AWS/Terraform orchestration is standard-library Python. They forward failure
as an error. If your organization blocks `.ps1` execution, do not change machine
execution policy. Equivalent commands preserve the same safety checks:

```powershell
.venv/Scripts/python.exe scripts/demo.py status
.venv/Scripts/python.exe scripts/demo.py prepare
.venv/Scripts/python.exe scripts/demo.py deploy
.venv/Scripts/python.exe scripts/demo.py verify
.venv/Scripts/python.exe scripts/demo.py cleanup
```

A command which changes AWS requires an interactive terminal and exact typed
confirmation. There is no `--yes` flag. **Implementing/testing these commands does
not authorize deployment now.** The apply/cleanup code paths have mock tests;
live AWS apply/destroy end-to-end behavior is not yet verified.

## What each command guarantees

- **prepare-demo:** authenticates, validates the initialized S3 backend and account
  context, validates Terraform, checks the approved ECR child digest and a completed
  zero-finding scan, checks Fargate rollout quota, then saves a fresh read-only dev
  plan. It prints each resource action, cost exposure and SHA256; it never applies.
- **deploy-demo:** refuses dirty source, a changed commit/account/backend/checksum,
  a consumed or older-than-one-hour plan, an unexpected resource/action or wrong
  image/security/capacity settings. It checks the ECR scan again. It applies only
  the saved dev plan after confirmation; it never plans/applies ECR/bootstrap.
- **verify-demo:** waits for stable ECS service, requires one running task with the
  approved digest, healthy ALB targets and correct health/readiness/version/metrics
  responses. It checks a recent CloudWatch sample without echoing log contents.
  A traceback or no recent log events fails verification.
- **cleanup-demo:** freshly plans dev destruction, prints every action, permits
  only deletions/no-ops on the 34 reviewed resource addresses (or a subset after
  partial deployment), and requires a separate confirmation. It checks AWS tasks,
  ALB, VPC, ENIs, tagged Elastic IPs, log group and remote state after teardown.
  Leftovers are failures. It never deletes the ECR repository or S3 backend.
- **status-demo:** uses AWS APIs and the remote dev state, not process status.
  Unknown/denied API calls fail rather than reporting clean. An absent S3 state
  object is handled only after AWS confirms Not Found. It remembers VPC IDs to
  inspect untagged service ENIs after partial cleanup. No resources are deleted.

Plans/approval records, sanitized status and verification results live under
ignored `.tools/demo/`. Plans can contain sensitive values: protect that directory
and never attach raw plans to Git/issues. The account is compared through a local
fingerprint; full account IDs, tokens and arbitrary service/log bodies are not
printed. AWS profile/region are explicit; inherited TF_VAR/TF_CLI_ARGS overrides
are removed so shell leftovers cannot silently change the approved demo. Review
any legitimate configuration change in source and regenerate plans.

Preparation uses `-lock=false` to avoid remote lock-object writes during read-only
review. Apply uses native S3 locking (`-lock-timeout=60s`); Terraform rejects stale
saved state. Do not prepare concurrently with another apply. Deployment records
are marked consumed **before** invoking apply: repeated execution cannot blindly
retry an interrupted plan. A fresh preparation is required. Repeated cleanup
regenerates a fresh plan, tolerates partial dev state and verifies AWS even when
there is nothing to destroy. An unchanged already-deployed plan is a no-op.

## Architecture and security explanation

Client -> public two-AZ HTTP ALB -> private target IP of a public-subnet ECS task
ENI -> FastAPI port8000. The task has a public IPv4 for outbound HTTPS to ECR and
CloudWatch without NAT; the task SG permits ingress only from the ALB SG. Public
IP assignment alone does not permit direct internet access. Private subnets remain
part of the architecture with no default NAT route. PostgreSQL SG is dormant
scaffolding; the demo does not start a cloud database.

Fargate Linux X86_64 uses 256 CPU units/512 MiB, one task. Image runs UID10001,
matching CPython3.12/musl wheels; a multistage digest-pinned official Alpine build
excludes secrets, Git and local environments, and removes runtime pip. Release
`git-9b18a3109aa2` resolves to approved AMD64 child digest
`sha256:e86be3d8597649995145a5e1633bfc4ccf19b8ca1185127ea6720d72d2bf0be1`.
The OCI index is separate from the platform digest; scan the child in ECR. Local
Trivy and ECR scans had zero findings at release; prepare checks current ECR results,
but a completed scan can age. Reassess/re-scan separately when advisory data changes.
Zero findings never establishes absence of vulnerabilities, especially bundled
native libraries. No image is pushed/rebuilt by these demo commands.

`/health` is DB-independent liveness. `/ready` is dependency readiness and the ALB
probe. Local Compose verifies PostgreSQL16 with SQLAlchemy pooling and psycopg;
AWS demo explicitly disables DB requirements. `/version` proves application
release, `/metrics` exposes Prometheus counters/latency. No production data belongs
in the public HTTP demo. `/docs`, metrics and version metadata are public as well.
Use a trusted CIDR instead of 0.0.0.0/0 when practical; that changes a resource key
and intentionally requires a new allowlist/security review instead of bypassing guards.

The execution role pulls only the existing repository and writes the app log
group; token authorization needs wildcard resource. Task role has no app AWS API
permissions. Seven-day log retention; no Insights, paid alarms, WAF or new log
archive. First use may create AWSServiceRoleForECS and
AWSServiceRoleForElasticLoadBalancing: `iam:CreateServiceLinkedRole` must be permitted.
`iam:PassRole`, dev resource lifecycle permissions and S3 state/lock permissions
are also required. A successful plan/IAM simulation is not proof against every
SCP/session/resource policy or capacity restriction.

Rollback circuit breaker is enabled; deployments allow 100% healthy minimum and
200% maximum (temporary second task). The first launch has no completed deployment
to roll back to. One task is a low-cost demo, not multi-AZ application availability.

## Costs and normal-day policy

Reviewed Sydney list rates (Task23, 2026-11-12), USD before credits/tax:

| Component | Approximate cost |
| --- | --- |
| One .25-vCPU/.5-GiB task | $0.0148/hour |
| One ALB | $0.0252/hour + $0.008/LCU-hour |
| At least 2 ALB IPv4 + 1 task IPv4 | $0.015/hour |
| Baseline | **$0.055/hour; $1.32/day** |
| Quiet example with 1 LCU and modest logs | **~$0.066/hour; $1.58/day** |
| Logs | $0.67/GB ingestion, $0.033/GB-month retention |

A 1-2 hour demo is roughly **$0.06-$0.14**, plus deployment/cleanup runtime, traffic,
log/storage usage, rounding and tax. It is not a guaranteed maximum. ALB/IP scaling
and abusive public traffic can increase costs. Setting desired_count=0 leaves
ALB and IPv4 charges active; use cleanup-demo. NAT/RDS/endpoints are absent. ECR
image storage and S3 state/version storage persist and are not literally free.
Credits offset eligible charges but are finite; do not rely on old balance figures.
Keep the local Docker/Compose demo ready if you cannot tolerate even small charges.

Pricing sources: [Fargate](https://aws.amazon.com/fargate/pricing/),
[ALB](https://aws.amazon.com/elasticloadbalancing/pricing/),
[IPv4](https://aws.amazon.com/vpc/pricing/) and Task23's saved regional rate evidence.
Task/ECS cluster/IAM/SG definitions have no standalone hourly charge. Public IPs
and tasks are implicit resources even though not aws_eip plan entries.

### Manual 1-2 hour checklist

1. Before deploying: set phone alarms for 60 and 90 minutes; assign a cleanup owner.
   Check credits in Billing/Free Tier and choose local-only if credits/money are tight.
2. Confirm clean approved source, current session and no other Terraform operator.
3. Run status; any existing billable dev infrastructure gets priority cleanup.
4. Prepare and inspect actions/hash/cost, then explicitly deploy. Record endpoint
   and start time. Infrastructure creation itself consumes part of the demo window.
5. Verify; present interview walkthrough. Watch CPU/memory, target health and logs.
6. At 60-90 minutes run cleanup; export required sanitized screenshots first because
   teardown deletes the dev log group. Do not close the terminal before verification.
7. Run status again. If cleanup fails, prioritize a new inspected cleanup plan;
   do not assume stopped local processes stopped AWS billing.
8. Recheck credits/Billing after usage settles; ECR/S3 remain intentionally.

### Budgets and independent safeguards (documentation only)

In AWS Billing console, use an alert-only monthly cost budget with a small amount
matching your actual tolerance (for example $1), plus actual thresholds at 50/80/100%
and a forecast alert if supported. Check whether the budget includes/excludes
credits: net-zero spend can conceal credit consumption, so monitor gross usage
and the Free Tier credit balance too. Enter email recipients privately; do not
commit them. Do not enable a new paid report, paid action or upgrade automatically.
No Budget or notification resource is provisioned by this workflow.

[AWS Budgets pricing](https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/)
and [budget actions](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-controls.html)
distinguish notifications from configured actions. **An alert does not stop AWS
charges.** Billing/alerts lag; a threshold is not a reliable hard cap.

For now, use an independent phone/calendar timer and a second person/check-in if
possible; they cost nothing in AWS and do not need cloud credentials. A future
independent cleanup runner could use a narrowly scoped OIDC role and the same
allowlist/checksum guards, after explicit authorization and sandbox testing.
Do not schedule untested Terraform destruction or store long-lived AWS keys.
Scheduling only desired_count=0 is insufficient because ALB/IP charges continue.
No scheduled destructive mechanism has been installed, enabled or tested here.

## Interview sequences

Deploy and verify before the interview timer; creation time is variable. Have
sanitized screenshots, this repository and local Compose ready if AWS is unavailable.

### Five-minute demonstration

- 0:00-0:45: explain ALB -> ECS task, SG trust and cost_saver outbound connectivity.
- 0:45-1:30: show immutable commit/tag/platform digest and zero-finding scan evidence.
- 1:30-2:30: call health/ready/version/metrics and show one healthy ALB target.
- 2:30-3:30: show structured CloudWatch logs and deployment circuit breaker settings.
- 3:30-4:15: explain Terraform review/hash/typed confirmation and separate S3/ECR state.
- 4:15-5:00: start approved cleanup or show its reviewed plan and prior cleanup
  evidence. Finish teardown after the interview; never claim it finished until status passes.

### Fifteen-minute technical walkthrough

- 0-3: architecture, subnets/routes/SGs, public task IP versus public ingress, no NAT/RDS.
- 3-5: secure multistage build, non-root, musllinux ABI, CA trust and ECR child scan.
- 5-8: Git review, backend ownership/native locking, plan JSON/allowlist/hash and stale-plan guards.
- 8-10: liveness/readiness, PostgreSQL local tests, image/version identity and target health.
- 10-12: logs, metrics, rollout health/circuit breaker and first-deployment rollback limits.
- 12-15: 1-2 hour cost arithmetic, credits/budget limitations, cleanup proof and recovery.

## Monitoring and troubleshooting

Use verify-demo for a bounded, sanitized health check. ECS events/stoppedReason,
ALB target-health reason codes and private CloudWatch logs provide details when
it fails. Never paste unredacted ARNs, tokens or log bodies into Git/evidence.
Recent log sampling is not a complete error history or an alarm.

```powershell
aws ecs describe-services --cluster aws-resilient-delivery-platform-dev --services aws-resilient-delivery-platform-dev --query 'services[].{running:runningCount,pending:pendingCount,desired:desiredCount}' --profile rdp-dev --region ap-southeast-2
aws freetier get-account-plan-state --query '{plan:accountPlanType,credits:accountPlanRemainingCredits,expires:accountPlanExpirationDate}' --profile rdp-dev --region ap-southeast-2
```

For private troubleshooting use AWS Console ECS task events, ALB target health and
CloudWatch Logs. Check permission failures, service-linked roles, image/log access,
HTTPS egress, desired task count and memory/CPU. No paid monitoring is needed for
this short manual demo. Don't weaken SGs or bypass scan findings to fix a failed launch.

### Failure/interruption recovery

A failed/timed-out/interrupted apply can leave billable partial infrastructure.
The attempted plan is marked consumed; never retry it blindly. Run status, inspect
AWS and preserve existing state. Confirm no Terraform process/operator is still
running. Do not delete state, migrate backends, force-unlock an active operation,
use -target or delete random AWS objects. Prepare-demo can resume create/no-op
partial deployments when the exact reviewed graph still holds. Unexpected
updates/replacements stop the workflow and require a separate reviewed recovery.
Cleanup-demo permits a dev-only subset of delete/no-op actions, generates a new
plan every time and prompts again. Account/backend/commit/hash/expiry checks still
apply. AWS errors are intentionally summarized rather than printing raw identifiers.

Cleanup verification checks running/pending ECS tasks, demo ALB, tagged VPCs,
remembered VPC ENIs, tagged Elastic IPs, log group and remote state resources.
AWS-managed untagged/orphan resources outside known VPCs or manually renamed
resources can escape this inventory; review Billing and the AWS Console as well.
If `.tools/demo/vpcs.json` is lost, restore the prior VPC ID from protected state
history for manual inspection. Do not claim zero charges from a zero-count report.
ECR images, S3 versions and account-wide service-linked IAM roles are intentionally
retained; no bootstrap/ECR destroy is part of this workflow.

## Testing and limits

Offline tests exercise cancellation, untrusted resources, replacements, wrong
images/accounts, tampered/stale/consumed plans, partial failure, dirty source,
missing state and leftover-resource detection. Wrappers are PowerShell syntax
checked and use Python argument lists instead of shell interpolation. A destructive
live end-to-end test is intentionally deferred until explicit deployment approval.
Run local app/PG tests with Compose and preserve its volume. On this Windows
machine application control can block the host psycopg DLL; verified container
unit tests provide Python3.12/Linux coverage without disabling OS security policy.

Normal days: run status-demo and keep dev infrastructure absent. No scheduled
cloud shutdown, AWS Budget, credential, resource or backend change was made by Task25.
