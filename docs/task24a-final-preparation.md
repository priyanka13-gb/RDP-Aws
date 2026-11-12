# Task 24A - final ECS demo preparation

2026-11-12. **GO for manual commit review; NO-GO for deployment approval until the final source commit and post-commit plan are complete.** No commit/push, apply/destroy, infrastructure creation, credential change, backend reconfiguration or remote state write was performed.

## Results and commit readiness

All pending Task 23 changes were reviewed: digest resolution and its release var-file, ECS dependency on ALB listener completion, documentation and sanitized evidence. No application/Docker changes are needed. Additional Task 24A changes: `.gitignore` exclusions for `.aws/` and `credentials.csv`, this report, the resource checklist, verification evidence and `scripts/prepare_ecs_demo_plan.py`.

Terraform fmt and validate passed. Existing mock-plan tests: dev16 + network5 + bootstrap1 + ECR1 = **23 passed, 0 failed**. The fresh real plan saved at `.tools/task24a/dev.tfplan` passed and matches every Task 23 managed resource address/type/action: **34 creates, 0 changes, 0 destroys, 0 replacements**. Digest, architecture, port, SG ingress, readiness, circuit breaker and retention assertions passed. No NAT, RDS, VPC endpoint or new ECR resources appear. No unexpected plan difference was found.

The review plan was generated from **uncommitted source**. It is not the requested final post-commit plan and must not be presented as one. Its raw output and JSON are ignored and contain account-specific data. SHA256 and sanitized counts are in `evidence/task24a/readiness.json`.

Secret scanning uses the same pinned Trivy scanner as Tasks 21-23 with `fs --scanners secret --exit-code 1`, over tracked and non-ignored untracked files. No finding is suppressed. Gitignore checks cover Terraform state/backups, `.terraform`, `.tfplan`, `.env`, `.secrets`, ignored local reports and AWS credential exports; no sensitive paths are currently tracked. Ignore rules do not make previously tracked secrets safe and are not a substitute for scanning. Do not stage raw plans, private logs or backend metadata.

### Manual commit commands - NOT executed

Review the paths and staged diff before committing. These paths contain only this preparation and Task 23 source/evidence:

```powershell
git status --short
git diff --check
git add -- .gitignore infra/envs/dev/main.tf infra/envs/dev/variables.tf infra/envs/dev/releases/task23.tfvars.example docs/ecs-first-deployment-readiness.md docs/task23-resource-inventory.md docs/task24a-final-preparation.md docs/task24a-resource-checklist.md evidence/task23 evidence/task24a scripts/prepare_ecs_demo_plan.py
git diff --cached --stat
git diff --cached --check
# Read all staged changes and approve their contents before this command:
git commit -m "Prepare digest-pinned ECS Fargate HTTP demo deployment"
git status --porcelain
```

The infrastructure commit will differ from the application release commit. Keep the application image digest and APP_VERSION/GIT_SHA pinned to the released application, not this later infrastructure commit.

### Post-commit plan - pending, NOT generated yet

After the manual commit and a clean working tree:

```powershell
.venv/Scripts/python.exe scripts/prepare_ecs_demo_plan.py
if ($LASTEXITCODE -ne 0) { throw 'Preparation failed; stop before deployment' }
```

The script refuses dirty source (verified during preparation), supplies Sydney/profile environment, runs a real read-only plan against the existing backend, saves `.tools/task24a/postcommit.tfplan`, checks the exact 34 resource addresses/actions and approved digest, and records source commit and plan hash in `.tools/task24a/postcommit-verification.json`. Review its full plan privately; matching resource actions does not substitute for reviewing every changed attribute. It never runs apply or changes backend configuration. Locking is disabled solely for read-only preparation to avoid creating remote lock objects under this task's restrictions. Use no concurrent Terraform runs.

## Deployment and cost checklist

See [every resource and cost driver](task24a-resource-checklist.md). Expected list-price baseline: **$0.055/hour, $1.32/day**, excluding LCU/log/traffic usage and tax. Example one LCU plus 0.1 GB/day logs: **~$0.06582/hour, $1.58/day**. These use Sydney AWS offer rates retrieved in Task 23 on 2026-11-12; complete sources and assumptions are in [Task 23 cost review](ecs-first-deployment-readiness.md#cost-estimate---usd-sydney-before-creditstax). This is not a spending cap.

Cost-bearing resources: ALB base .0252/hour; at least two ALB IPv4s .010/hour; one task .0148/hour plus its IPv4 .005/hour; .008 per ALB LCU-hour; logs .67/GB ingested and .033/GB-month stored. Other planned networking/IAM objects have no standalone hourly rate. Image/state storage and traffic can add charges. Scaling tasks to zero leaves the ALB/IP baseline billed. Teardown, not task scaling alone, ends those costs.

Read-only AWS checks refreshed: authentication works; backend bucket is in Sydney; dev state and lock object are absent; approved image child exists and ECR scan is COMPLETE with zero findings. Free plan is ACTIVE with **$120 credits** at review time, expiring 2027-05-05 09:35:47 UTC unless consumed earlier. Credits are not an unlimited free deployment. No AWS account upgrade was performed.

Checklist before approval:

- [ ] Manually commit reviewed preparation and confirm clean Git.
- [ ] Run post-commit plan preparation and inspect all values/actions; stop on differences.
- [ ] Accept short-lived **public HTTP80** exposure, including public /metrics, /docs and version metadata. This is not HTTPS; no credentials, private information or real-user data may be sent. Narrow ALB CIDRs to trusted /32 if desired, then commit/replan.
- [ ] Confirm the demo duration and teardown owner/time. Budget for ALB/IP charges throughout.
- [ ] Reconfirm IAM permission context is Sydney and creation of absent ECS/ELB service-linked roles is acceptable.
- [ ] Obtain explicit deployment approval for a fresh locked plan before any apply.

## Security and IAM review

Only ALB SG reaches ECS SG port8000; no public CIDR task ingress exists. Tasks receive public IPs for outbound ECR/logging without NAT, but those IPs do not bypass SG rules. ALB forwards to private task IPs. Task HTTPS egress is broad. Private route tables have no NAT/default route. PostgreSQL SG is unused scaffolding, not an RDS instance.

Linux X86_64, CPU256/memory512, UID10001, port8000 and digest `sha256:e86be3d8597649995145a5e1633bfc4ccf19b8ca1185127ea6720d72d2bf0be1` are preserved. APP_VERSION `git-9b18a3109aa2`, GIT_SHA `9b18a3109aa2fd1d3bc6a2dc0ffb0fc17ec27823`. No database or SSM secrets configured. Execution role can pull only the selected repository and write to its log group (ECR authorization token requires wildcard resource). Task role has no app AWS permissions. Logs retain seven days. ECS circuit breaker rollback is enabled; the first deployment has no previous completed release to roll back to.

Task 23 IAM evidence was reviewed: sampled create-role, inline policy, PassRole, CreateServiceLinkedRole and logs actions allowed. Region-context simulation allowed sampled EC2/ECS/ELB/backend actions. Initial missing-region simulation denials were contextual, not proof of Sydney denial. Simulation is not exhaustive and does not guarantee SCP, session/resource policy or create-time capacity success. Required permissions include EC2 VPC/subnet/SG/routes/tags lifecycle; ECS cluster/service/task definition lifecycle; ELB/listener/target-group lifecycle; IAM role/policy/PassRole and first-use CreateServiceLinkedRole; logs; S3 list/get/put state and get/put/delete lock. Do not grant broad policies automatically.

NoSuchEntity was previously confirmed for AWSServiceRoleForECS and AWSServiceRoleForElasticLoadBalancing. ECS/ELB can create them on first use if permitted. They are two implicit IAM prerequisites outside the 34 Terraform-managed addresses; no hourly cost, and they may persist after teardown. Regional Fargate quota30 vCPU exceeds .25 steady/.5 rollout requirement; prior VPC quota5 and ALB quota50 were sufficient. Real provisioning permissions/capacity remain subject to apply-time validation.

## Deployment after explicit approval - commands only, NOT executed

The post-commit review plan uses no remote lock writes. After deployment approval, create and review a fresh **locked** execution plan. Do not use stale/unlocked plans, -target, -reconfigure or migration:

```powershell
$env:AWS_PROFILE = 'rdp-dev'
$env:AWS_REGION = 'ap-southeast-2'
$env:AWS_DEFAULT_REGION = 'ap-southeast-2'
if (git status --porcelain) { throw 'Source must be clean' }
terraform -chdir=infra/envs/dev plan -input=false -lock-timeout=60s '-var-file=releases/task23.tfvars.example' '-out=../../../.tools/task24a/approved.tfplan'
if ($LASTEXITCODE -ne 0) { throw 'Plan failed' }
# Inspect and confirm still 34 creates, zero updates/deletes/replacements and approved digest.
# Stop if any action or security/cost attribute differs unexpectedly.
terraform -chdir=infra/envs/dev apply '../../../.tools/task24a/approved.tfplan'
if ($LASTEXITCODE -ne 0) { throw 'Partial apply possible: follow failure procedure below' }
aws ecs wait services-stable --cluster aws-resilient-delivery-platform-dev --services aws-resilient-delivery-platform-dev --profile rdp-dev --region ap-southeast-2
```

Native S3 locking writes a temporary lock object during these future approved commands. That action has not been taken during preparation.

## Smoke tests and monitoring after deployment

```powershell
$base = (terraform -chdir=infra/envs/dev output -raw application_url).Trim()
foreach ($path in @('/health','/ready','/version','/metrics')) {
  $r = Invoke-WebRequest -Uri "$base$path" -UseBasicParsing
  if ($r.StatusCode -ne 200) { throw "Failed endpoint: $path" }
}
$v = Invoke-RestMethod "$base/version"
if ($v.app_version -ne 'git-9b18a3109aa2' -or $v.git_sha -ne '9b18a3109aa2fd1d3bc6a2dc0ffb0fc17ec27823') { throw 'Wrong release' }
aws ecs describe-services --cluster aws-resilient-delivery-platform-dev --services aws-resilient-delivery-platform-dev --query 'services[].{running:runningCount,pending:pendingCount,desired:desiredCount,events:events[0:5].[message]}' --profile rdp-dev --region ap-southeast-2
aws logs tail /ecs/aws-resilient-delivery-platform-dev --since 15m --profile rdp-dev --region ap-southeast-2
$dns = (terraform -chdir=infra/envs/dev output -raw alb_dns_name).Trim()
$lbArn = (aws elbv2 describe-load-balancers --query "LoadBalancers[?DNSName=='$dns'].LoadBalancerArn | [0]" --output text --profile rdp-dev --region ap-southeast-2).Trim()
$tgArn = (aws elbv2 describe-target-groups --load-balancer-arn $lbArn --query 'TargetGroups[0].TargetGroupArn' --output text --profile rdp-dev --region ap-southeast-2).Trim()
aws elbv2 describe-target-health --target-group-arn $tgArn --query 'TargetHealthDescriptions[].TargetHealth' --profile rdp-dev --region ap-southeast-2
```

Verify running tasks' `containers[].imageDigest` against the approved AMD64 digest privately with `aws ecs describe-tasks`; do not paste account-specific task ARNs into evidence. Observe ECS CPU/Memory, ALB HealthyHostCount/5xx/TargetResponseTime in CloudWatch; no custom alarms/Insights are provisioned. This is manual monitoring, not an automatic spending or availability guard.

## Partial apply failure procedure

1. Stop retries and preserve the exact CLI error privately. Record time, plan hash and source commit. A failed apply can leave billable resources running and Terraform may already have written partial state.
2. Do not edit/delete state, manually delete newly created objects, force-unlock an active operation, reinitialize/migrate backend, or repeat the old saved plan blindly. Confirm the previous Terraform process has ended and no other operator is applying.
3. Inspect state and AWS read-only status/events/logs to identify completed resources. Check service-linked-role creation, image-pull/log permissions, task stoppedReason, target health and network reachability. A first-deploy circuit breaker cannot restore a nonexistent previous deployment.
4. Prepare a **new** plan using the same committed configuration and existing partial state. Review exact drift/actions and any remaining charges. Request approval before retrying or rolling back. If AWS has a resource absent from state, review ownership/import separately; never assume safe deletion or automatic import.
5. If abandoning the demo, prepare a reviewed destroy plan against the **dev root only**, using the actual state. Export needed logs privately before teardown. Do not remove bootstrap/ECR states, buckets or images. Reconcile remaining resources afterward; billing data may lag.

Read-only inspection commands (outputs can contain identifiers, keep private):

```powershell
terraform -chdir=infra/envs/dev state list
aws ecs describe-services --cluster aws-resilient-delivery-platform-dev --services aws-resilient-delivery-platform-dev --profile rdp-dev --region ap-southeast-2
aws ecs list-tasks --cluster aws-resilient-delivery-platform-dev --desired-status STOPPED --profile rdp-dev --region ap-southeast-2
aws logs tail /ecs/aws-resilient-delivery-platform-dev --since 30m --profile rdp-dev --region ap-southeast-2
```

## Teardown and cost verification - future separate approval

Scaling desired count to zero stops compute but **does not stop ALB/IP charges**. After explicit teardown approval:

```powershell
terraform -chdir=infra/envs/dev plan -destroy -input=false -lock-timeout=60s '-var-file=releases/task23.tfvars.example' '-out=../../../.tools/task24a/teardown.tfplan'
if ($LASTEXITCODE -ne 0) { throw 'Teardown planning failed' }
# Inspect only the dev state resources; approve this destroy plan first.
terraform -chdir=infra/envs/dev apply '../../../.tools/task24a/teardown.tfplan'
if ($LASTEXITCODE -ne 0) { throw 'Teardown incomplete; inspect remaining resources and costs' }
terraform -chdir=infra/envs/dev state list
aws elbv2 describe-load-balancers --query 'LoadBalancers[].LoadBalancerName' --profile rdp-dev --region ap-southeast-2
aws ecs list-clusters --profile rdp-dev --region ap-southeast-2
aws ec2 describe-network-interfaces --filters Name=tag:Project,Values=aws-resilient-delivery-platform --query 'NetworkInterfaces[].{Status:Status,Description:Description}' --profile rdp-dev --region ap-southeast-2
aws logs describe-log-groups --log-group-name-prefix /ecs/aws-resilient-delivery-platform-dev --query 'logGroups[].{name:logGroupName,bytes:storedBytes}' --profile rdp-dev --region ap-southeast-2
aws freetier get-account-plan-state --query '{plan:accountPlanType,status:accountPlanStatus,credits:accountPlanRemainingCredits,expires:accountPlanExpirationDate}' --profile rdp-dev --region ap-southeast-2
```

Tag filters can miss service-managed ENIs; also inspect VPC ENIs privately using the pre-teardown VPC ID and confirm task/public IPv4 allocations are gone. Verify the demo ALB is absent, tasks stopped, and dev log group removed. Service-linked roles may remain without hourly charges. S3 versions and ECR storage are intentionally retained. Review Billing/Free Tier and available Cost Explorer usage (if enabled/allowed) after billing settles; absence of instant charges does not establish zero usage. Do not activate paid monitoring or upgrade the account just to audit this demo.

## Stop point

Git is **not clean**: the reviewed infrastructure/preparation changes remain uncommitted by instruction. Fresh **pre-commit review** plan passed; **post-commit saved plan is pending**. GO for commit review, NO-GO for deployment until that required commit/plan and explicit deployment approval. Nothing has been deployed.
