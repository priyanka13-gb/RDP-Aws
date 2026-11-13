# Monitoring and failure recovery

Task 30 adds read-only observation and local Docker fault drills. It does not
deploy, register task definitions, change a service, create alarms, or inject an
AWS failure. The current read-only observation found no deployed demo cluster;
there is no current healthy rollback baseline. **Live rollback is NOT VERIFIED.**

## Existing configuration reviewed

| Control | Existing configuration |
| --- | --- |
| ECS rolling deployment | Circuit breaker enabled, rollback enabled, steady-state wait enabled |
| Capacity | Fargate Linux X86_64, 256 CPU units, 512 MiB; UID 10001 |
| Deployment capacity | Minimum healthy 100%, maximum 200%; health grace 60 seconds |
| Container liveness | `/health` on port 8000; 30-second interval, 5-second timeout, 3 retries, 30-second start period |
| ALB readiness | `/ready`, HTTP 200, port 8000; 30-second interval, 5-second timeout; healthy threshold 2, unhealthy threshold 3 |
| Logs | awslogs, `/ecs/aws-resilient-delivery-platform-dev`, Sydney, prefix `app`, seven-day retention |
| Network | ALB HTTP demo listener; task ingress on 8000 restricted to ALB security group |

No Terraform, runtime image, application, cleanup confirmation, plan expiration,
or cost limit was changed. HTTP is suitable only for this short public demo;
do not send credentials or personal data. Cost_saver still has no NAT/RDS.

## Read-only monitoring

From the repository root:

```powershell
.venv/Scripts/python.exe scripts/demo.py monitor
.venv/Scripts/python.exe scripts/monitor_demo.py --require-rollback-baseline
# Equivalent convenience wrapper for the first command:
./scripts/monitor-demo.ps1
```

The existing profile/account/backend guards run first. The monitor uses only
STS/S3/ECR context checks, ECS Describe/List, ELB Describe, Logs Describe/Filter,
and CloudWatch GetMetricStatistics. The operator needs those read permissions;
no new role or policy is installed. Permission or authentication failures make
health unknown and invalidate any old healthy snapshot.

The sanitized `.tools/demo/monitor.json` reports current rollout state, hashed
task-definition identifiers, task/target health, seven-day retention, a bounded
log sample, stopped-task code counts, CPU/memory, ALB latency and target 5XX.
Raw log bodies, ARNs, task IDs, account IDs and stop-reason text are withheld.
Missing metrics are null, not zero. The log sample covers up to 100 events in
15 minutes; it is not proof of error-free history. Metrics can arrive late.
No log events alone does not prove delivery. Inspect logs privately if needed.

The baseline guard requires the **current PRIMARY deployment COMPLETED**, the
approved image digest, healthy running tasks, healthy targets, expected target
configuration, breaker and logging settings, and no sampled traceback. It is a
point-in-time prerequisite, not a promise that a future rollback will succeed.
Historical evidence from a deleted cluster is insufficient. Run HTTP smoke tests
and review private service events as well. Normal monitoring returns success for
an observed absent deployment; the baseline-required command intentionally fails.

This is an operator-invoked snapshot, not a continuous alarm or automatic cost
cap. CloudWatch API/log retrieval may incur usage charges. Keep the existing demo
time budget and cleanup workflow; inspect billing separately.

## Safe local failure drills

```powershell
.venv/Scripts/python.exe scripts/local_failure_drill.py
# Optional reviewed local image:
.venv/Scripts/python.exe scripts/local_failure_drill.py --image rdp-release:git-9b18a3109aa2
```

Requires an existing Linux AMD64 image with UID 10001:10001 and Docker. It does
not pull, rebuild, push or contact AWS. Each container has network disabled,
no published ports, no volume mounts, a 512 MiB/0.25 CPU limit and empty database
configuration. Temporary command overrides inject faults without changing the
image or production source. Only containers created and labelled by this run
are removed; PostgreSQL volumes and existing containers are preserved.

| Scenario | Expected observation |
| --- | --- |
| Healthy baseline | `/health` and `/ready` 200; Docker healthy |
| Unhealthy application | `/health` 503, `/ready` 200; Docker unhealthy |
| Failed readiness | `/health` 200, `/ready` 503; Docker healthy |
| Startup failure | Exit 1 before an HTTP server starts |
| Healthy recovery | Original command restored in a new container; both endpoints 200 |

Readiness failure demonstrates why container liveness alone is insufficient.
Docker does not perform an ECS rollback. Local recovery creates a fresh healthy
container, so these results must not be described as an AWS rollback test.
The actual timeline is in [the local drill record](incidents/local-failure-drill.md).

## Controlled AWS rollback drill: NOT EXECUTED

AWS documents that circuit-breaker rollback needs a previously completed
deployment: [ECS circuit breaker](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/deployment-circuit-breaker.html).
The first-ever deployment cannot establish this proof by failing. Breaker
thresholds and health-check timing affect recovery; do not promise an exact
rollback duration. Standard service metrics are described in
[ECS service utilization](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service_utilization.html).

Before requesting separate approval:

1. Complete a separately approved healthy demo deployment. Run the baseline
   guard and existing `scripts/verify-demo.ps1`; save HTTP health/readiness proof.
2. Privately capture the current task definition ARN and complete definition
   under ignored `.tools/rollback-drill/`. Record its fingerprint, approved image
   digest, target health and timestamp. Confirm no competing operator/deployment.
3. Review a single bad revision retaining the approved image, security groups,
   IAM, networking, resources and logging. Override only the container command
   with `python -c "raise RuntimeError('CONTROLLED_STARTUP_FAILURE')"`. Do not
   change ports, security groups, health thresholds, secrets or scanning.
4. Obtain explicit approval for registration, service update, a maximum
   15-minute observation window, emergency restoration, and deregistration of
   the bad revision. Confirm the existing cleanup deadline leaves enough time.
   Up to two tasks can overlap at 200%; allow extra Fargate and public IPv4 cost.
   A healthy starting deployment reduces risk but does not guarantee no outage.

Only after that separate approval, an operator can execute the following
commands with privately populated variables. These are a runbook, not a script
invoked by monitoring. `bad-task-definition.json` must contain only ECS
registerable fields; strip response-only ARN, revision, status, registration
metadata, compatibilities and requiredAttributes. Preserve reviewed fields such
as family, roles, containerDefinitions, networkMode, CPU, memory, runtimePlatform
and requiresCompatibilities. Write UTF-8 without BOM on Windows PowerShell 5.1.

```powershell
$cluster = 'aws-resilient-delivery-platform-dev'
$service = $cluster
# $baseline is the privately saved known-good task-definition ARN.
# $bad is assigned from the reviewed registration response; do not publish ARNs.
$bad = aws ecs register-task-definition --cli-input-json file://.tools/rollback-drill/bad-task-definition.json --query taskDefinition.taskDefinitionArn --output text --profile rdp-dev --region ap-southeast-2
aws ecs update-service --cluster $cluster --service $service --task-definition $bad --profile rdp-dev --region ap-southeast-2 > .tools/rollback-drill/update-private.json
.venv/Scripts/python.exe scripts/demo.py monitor
# Repeat bounded read-only observations; do not automatically retry mutation.
```

Record the bad deployment ID privately. Success requires evidence of its FAILED
rollout/circuit-breaker event followed by the original definition becoming
PRIMARY COMPLETED, the original image running healthy, healthy ALB targets and
successful HTTP `/health` and `/ready`. Capture events before ECS history expires.
`services-stable` by itself does not prove rollback occurred.

At the approved deadline, stop the drill. If emergency restoration was explicitly
approved, restore the saved known-good definition, then monitor and smoke-test:

```powershell
aws ecs update-service --cluster $cluster --service $service --task-definition $baseline --profile rdp-dev --region ap-southeast-2 > .tools/rollback-drill/restore-private.json
# After recovery, and only with the approved cleanup authorization:
aws ecs deregister-task-definition --task-definition $bad --profile rdp-dev --region ap-southeast-2 > .tools/rollback-drill/deregister-private.json
```

Otherwise request operator approval before a recovery mutation. Preserve evidence;
never delete state or force-unlock to repair a service. Review a read-only
Terraform plan for drift after manual changes, without applying it blindly.
Use the existing separately confirmed `cleanup-demo.ps1` for normal dev teardown;
do not destroy bootstrap/ECR or PostgreSQL volumes. Verify status, ENIs/public IPs,
ALB, VPC and billing after cleanup. Failed recovery does not suspend cost limits.

Use [the postmortem template](incidents/postmortem-template.md) and distinguish
automatic rollback, manually restored service and unverified recovery.
