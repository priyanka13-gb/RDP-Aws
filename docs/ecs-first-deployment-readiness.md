# Task 23 ? first ECS Fargate deployment readiness

Reviewed 2026-11-12. **Conditional GO for a short, non-sensitive HTTP demonstration after explicit apply approval. NO-GO for production traffic or credentials over HTTP.** No apply/destroy was executed and no AWS infrastructure, backend configuration or remote state was changed. Git changes are uncommitted and have not been pushed.

## Real plan and changes

The real dev-root plan succeeded against its existing S3 backend: **34 to add, 0 to change, 0 to destroy, 0 replacements**. Prior managed dev resources: zero. Full resource addresses: [task23-resource-inventory.md](task23-resource-inventory.md). The plan includes:

| Planned type | Count |
| --- | ---: |
| VPC / Internet Gateway / public default route | 1 / 1 / 1 |
| Subnets (two public, two private) | 4 |
| Route tables / associations | 3 / 4 |
| Dedicated SGs / adopted default SG | 3 / 1 |
| SG ingress / egress rules | 3 / 3 |
| ALB / target group / HTTP listener | 1 / 1 / 1 |
| ECS cluster / task definition / service | 1 / 1 / 1 |
| IAM roles / inline execution policy | 2 / 1 |
| CloudWatch log group | 1 |

No NAT, Elastic IP resource, RDS, VPC endpoint, SSM parameter, ECR repository, custom KMS key, WAF, paid monitoring add-on or autoscaling resource is proposed. ALB/task public IPv4 allocations are implicit and billable even though no aws_eip resource appears. The default SG resource manages only the new VPC's default group. The PostgreSQL SG/rules are inert scaffolding retained from the network module; no database is deployed.

Changes prepared:

- `infra/envs/dev/variables.tf`: optional validated `image_digest` resolves against the existing ECR repository; legacy explicit `container_image` remains available. Digest takes precedence.
- `infra/envs/dev/main.tf`: use digest-based URI; make ECS wait for the ALB module (including listener), preventing service creation before target-group association.
- `infra/envs/dev/releases/task23.tfvars.example`: account-independent release settings, desired count 1, no NAT/RDS, correct version/commit.
- This report, resource inventory and sanitized `evidence/task23/` files.

The release is pinned to **AMD64 child** `sha256:e86be3d8597649995145a5e1633bfc4ccf19b8ca1185127ea6720d72d2bf0be1`, rather than OCI index `sha256:7c776aa38d2289c3956c2d934a5c7dfc16bab2bfdbe51f1528cabdeebf6075c8`. ECR describes the child with no tags, which is expected; the immutable release tag belongs to the index. Child presence and COMPLETE scan with zero findings were verified through AWS APIs. APP_VERSION is `git-9b18a3109aa2`, GIT_SHA is `9b18a3109aa2fd1d3bc6a2dc0ffb0fc17ec27823`.

## Backend and verification

Authenticated with profile `rdp-dev`, region `ap-southeast-2`. Existing backend metadata points to bucket `rdp-tfstate-sydney-be4bb3dfae`, key `aws-resilient-delivery-platform/dev/terraform.tfstate`, encryption and native S3 locking enabled. Bucket location is Sydney. Cached backend metadata has null region/profile fields: these are supplied explicitly through AWS environment variables; it was not reconfigured. Dev state and lock object HEAD calls returned Not Found. Terraform's real plan confirmed no prior managed dev resources. Bootstrap and ECR states were not touched.

- `terraform fmt -check -recursive`: passed.
- `terraform -chdir=infra/envs/dev validate`: passed.
- `terraform -chdir=infra/envs/dev init -backend=false -input=false -lockfile=readonly` with explicit AWS environment: passed; no migration/reconfigure performed.
- Existing mock-plan tests: dev 16, network 5, bootstrap 1, ECR 1: **23 passed, zero failed**.
- Real plan with release var-file: passed. Automated JSON checks confirmed approved digest, X86_64, 256 CPU/512 MiB, public task IP, rollback, /ready, seven-day retention, and no NAT/RDS/unrelated resources.

Raw plan and JSON are ignored under `.tools/task23/`; they contain account-specific metadata and must not be committed. Sanitized plan summary and AWS checks are under `evidence/task23/`. The review plan used `-lock=false` solely to avoid creating a remote lock object during this read-only review; no state write occurred. Do not apply that unlocked review plan. Generate a fresh locked plan after approval and with no concurrent Terraform run.

Tooling failures corrected: PowerShell split an unquoted var-file argument; retry using an argument list passed. An initial backend-disabled init omitted AWS_REGION; retry with explicit region passed. IAM simulation without region context returned explicit denies from regional policy conditions; contextual retry was allowed. Preserve both simulation reports so this distinction remains visible.

## Security and availability

VPC `10.0.0.0/16`, dynamically selected Sydney AZs `ap-southeast-2a/b`, public CIDRs `10.0.0.0/24`, `10.0.1.0/24`, private `10.0.10.0/24`, `10.0.11.0/24`. Only public subnets have an IGW default route. Private tables have no NAT/default egress route. ECS uses public ENIs to pull from ECR and send logs without NAT; the ALB targets their private IPs.

- Internet ? ALB TCP80; ALB SG ? task SG TCP8000 only. No direct public task ingress.
- ALB egress only to tasks:8000. Task egress permits HTTPS to internet and PostgreSQL SG:5432; default VPC SG is cleared. HTTPS egress is broad, not destination allowlisted. Amazon-provided DNS is available with VPC DNS enabled.
- Task `awsvpc`, Linux X86_64, Fargate 1.4.0, 0.25 vCPU/0.5 GiB is a supported pair; no ARM image mismatch. UID10001, image command preserved, liveness /health; ALB readiness /ready.
- Execution role scopes image-pull permissions to the existing repository and logs writes to the application group. Authorization-token action requires wildcard scope. Task role has no application AWS permissions. Trust policies constrain source account and ECS region ARN.
- No SSM secrets selected, no database URL/password, no RDS. No credentials were embedded. Public endpoints include /metrics, /docs and version metadata; use no sensitive data. Narrow `alb_ingress_cidrs` to a trusted client /32 if appropriate, then regenerate the plan because the SG resource address changes.
- Seven-day log retention; no custom alarms, Container Insights, ALB access-log bucket or HTTPS certificate added. Monitor manually for this short demo. Production requires TLS, authentication/metrics exposure review, alarms and capacity/availability decisions.
- Circuit breaker and rollback enabled; min healthy 100%, max 200%, grace period 60s. A rollout may temporarily run two tasks (0.5 vCPU total). **First deployment has no previous completed deployment to roll back to**; if it fails, inspect events/logs and clean up after approval.
- One task is intentionally inexpensive, not highly available despite the two-AZ ALB. No production load/RDS TLS test is claimed.

## Permissions, quotas and Free plan

Read-only EC2, ECS, ELB, ECR and S3 checks succeeded. Existing counts: 1 VPC, 0 ECS clusters, 0 load balancers. Quotas: VPC 5; ALB 50; regional Fargate On-Demand vCPU 30. This deployment needs one additional VPC, one ALB, 0.25 vCPU steady/0.5 during rollout. Actual capacity, ENI and other service limits can still fail during creation.

IAM GetRole returned NoSuchEntity for `AWSServiceRoleForECS` and `AWSServiceRoleForElasticLoadBalancing`. AWS may create these two account-wide service-linked roles on first use; they are additional implicit IAM objects outside the 34 Terraform addresses and have no direct hourly fee. Confirm this automatic first-use creation is acceptable. Do not pre-create them during this review.

IAM simulation allowed sampled role creation/inline policy/PassRole/CreateServiceLinkedRole and logs actions; contextual simulation with `aws:RequestedRegion=ap-southeast-2` allowed VPC/subnet, ECS cluster/service/task definition, ELB creation and S3 get/put/delete. This is sampled identity-policy evidence, not a complete proof against SCPs, session policies, resource policies or resource-specific conditions. Apply also needs SG/routes/tags/delete operations and native state-lock get/put/delete; refresh permissions at deployment time. No policies or credentials were modified.

AWS Free Tier API reports ACTIVE FREE plan, **US$120 remaining credits**, expiration **2027-05-05 09:35:47 UTC** at review time. Credits and expiration can change; account usage can consume them earlier. [AWS Free plan terms](https://aws.amazon.com/free/terms/) end the Free plan at credit exhaustion or six months, whichever comes first. Do not assume unlimited free ALB/Fargate use. The [supported-service list](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html) includes ECS, ECR, VPC, ELB and CloudWatch for this experience; individual features and organization policies can still be restricted. No upgrade or advanced feature activation was performed.

## Cost estimate ? USD, Sydney, before credits/tax

Rates retrieved from AWS public regional offer catalogs on 2026-11-12:
[Fargate](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonECS/current/ap-southeast-2/index.json),
[ALB](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSELB/current/ap-southeast-2/index.json),
[CloudWatch](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/ap-southeast-2/index.json),
[VPC](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonVPC/current/ap-southeast-2/index.json).
Relevant extracted rows are saved in evidence. No ReservedLCUs or Outposts rates were used.

| Component / assumption | USD/hour | USD/24h |
| --- | ---: | ---: |
| Fargate: .25?.04856 vCPU + .5?.00532 GB | .01480 | .35520 |
| One ALB base | .02520 | .60480 |
| Public IPv4: 2 ALB + 1 task, .005/address/hour | .01500 | .36000 |
| Baseline before LCU/logs/traffic | **.05500** | **1.32000** |
| Example 1 average ALB LCU ? .008 | .00800 | .19200 |
| Example 0.1 GB logs ingested/day ? .67/GB | .00279 average | .06700 |
| Example 0.7 GB retained logs ? .033/GB-month | ~.00003 | ~.00077 |
| Example total | **~.06582** | **~1.57977** |

Budget **US$1.32?1.59/day for a quiet demo**, plus variable traffic/storage and taxes. Not an upper bound: high request counts, 4xx scanning, log volume and ALB scaling can increase consumption. ALB has at least two public IPs; additional ALB addresses and transient second-task addresses add charges. Each extra task adds about .0198/hour including its IPv4. At 730 hours, baseline is ~$40.15/month; example ~$48.05/month. Standard Fargate 20-GB ephemeral allocation is included; no extra storage configured.

VPC/subnets/IGW/routes/security groups/IAM/ECS cluster have no standalone hourly fee in this design. NAT/RDS/endpoints cost zero because absent. Same-VPC ALB-to-target traffic has no regional cross-zone fee per [AWS networking guidance](https://aws.github.io/aws-networking-best-practices/foundation/regions-azs/). Ordinary inbound internet transfer is free; outbound and other cross-AZ/service paths can be charged. [AWS data transfer pricing](https://aws.amazon.com/ec2/pricing/on-demand/) provides an aggregate 100-GB/month internet egress allowance where eligible; its availability is account-wide, not a per-app allocation. This estimate assumes negligible demo egress within remaining allowance; price high-volume egress separately before use.

Existing ECR storage and versioned S3 state requests/storage remain additional usage after teardown. Their costs depend on compressed image storage and retained state versions, not the 166-MB uncompressed local image size. CloudWatch query/scanned-byte and optional alarm charges are outside this estimate. Fargate pulls from same-region ECR do not require a NAT processing fee here. Promotional credits may offset eligible usage but do not reduce the consumption rate. $120 would fund roughly 76 quiet-example days **if no other usage consumed credits**; this is not a promised coverage duration.

## Commands after separate deployment approval ? NOT EXECUTED

Run from repository root in PowerShell. Review/commit the infrastructure changes first; never include plans/backend/account-specific files. Preserve the application image tag and digest independently of that infrastructure commit.

```powershell
$env:AWS_PROFILE = 'rdp-dev'
$env:AWS_REGION = 'ap-southeast-2'
$env:AWS_DEFAULT_REGION = 'ap-southeast-2'
terraform -chdir=infra/envs/dev validate
terraform -chdir=infra/envs/dev plan -input=false -lock-timeout=60s '-var-file=releases/task23.tfvars.example' '-out=../../../.tools/task23/approved.tfplan'
if ($LASTEXITCODE -ne 0) { throw 'Plan failed' }
# Review all resource actions and costs, then explicitly approve this saved plan.
terraform -chdir=infra/envs/dev apply '../../../.tools/task23/approved.tfplan'
if ($LASTEXITCODE -ne 0) { throw 'Deployment failed; inspect partial state and costs' }
aws ecs wait services-stable --cluster aws-resilient-delivery-platform-dev --services aws-resilient-delivery-platform-dev --profile rdp-dev --region ap-southeast-2
```

Do not run init -reconfigure, migrate-state, change backend or -target. If the existing backend is not initialized on another machine, stop and perform a separate backend review. The reviewed plan is ignored at `.tools/task23/dev.tfplan` and must not substitute for a fresh approved locked plan.

### Smoke tests and monitoring after apply

```powershell
$base = (terraform -chdir=infra/envs/dev output -raw application_url).Trim()
foreach ($path in @('/health','/ready','/version','/metrics')) {
  $response = Invoke-WebRequest -Uri "$base$path" -UseBasicParsing
  if ($response.StatusCode -ne 200) { throw "Smoke test failed: $path" }
}
$version = Invoke-RestMethod "$base/version"
if ($version.app_version -ne 'git-9b18a3109aa2' -or $version.git_sha -ne '9b18a3109aa2fd1d3bc6a2dc0ffb0fc17ec27823') { throw 'Wrong release metadata' }
aws ecs describe-services --cluster aws-resilient-delivery-platform-dev --services aws-resilient-delivery-platform-dev --query 'services[].{running:runningCount,desired:desiredCount,pending:pendingCount,events:events[0:5].[message]}' --profile rdp-dev --region ap-southeast-2
aws logs tail /ecs/aws-resilient-delivery-platform-dev --since 15m --profile rdp-dev --region ap-southeast-2
```

For target health, obtain the actual ARN from the scoped load balancer rather than guessing its hashed name:

```powershell
$albDns = (terraform -chdir=infra/envs/dev output -raw alb_dns_name).Trim()
$lbArn = (aws elbv2 describe-load-balancers --query "LoadBalancers[?DNSName=='$albDns'].LoadBalancerArn | [0]" --output text --profile rdp-dev --region ap-southeast-2).Trim()
$tg = (aws elbv2 describe-target-groups --load-balancer-arn $lbArn --query 'TargetGroups[0].TargetGroupArn' --output text --profile rdp-dev --region ap-southeast-2).Trim()
aws elbv2 describe-target-health --target-group-arn $tg --query 'TargetHealthDescriptions[].TargetHealth' --profile rdp-dev --region ap-southeast-2
```

Review ECS task stoppedReason if rollout fails; record privately, since unrestricted AWS output can contain account ARNs. In CloudWatch console review CPUUtilization/MemoryUtilization for the ECS service and HealthyHostCount/HTTPCode_Target_5XX_Count/TargetResponseTime for its ALB/target group. No alarm is provisioned. Check AWS Billing Free Tier credits and usage after the demo; billing data can lag.

### Teardown procedure ? separate explicit approval required, NOT EXECUTED

Scaling desired_count to zero stops task compute but leaves ALB and at least two public IPv4 addresses billed. For full dev teardown after approval:

```powershell
terraform -chdir=infra/envs/dev plan -destroy -input=false -lock-timeout=60s '-var-file=releases/task23.tfvars.example' '-out=../../../.tools/task23/teardown.tfplan'
if ($LASTEXITCODE -ne 0) { throw 'Teardown plan failed' }
# Inspect: only dev resources, never bootstrap/ECR. Approve before running:
terraform -chdir=infra/envs/dev apply '../../../.tools/task23/teardown.tfplan'
terraform -chdir=infra/envs/dev state list
aws ecs list-clusters --profile rdp-dev --region ap-southeast-2
aws elbv2 describe-load-balancers --query 'LoadBalancers[].{Name:LoadBalancerName,State:State.Code}' --profile rdp-dev --region ap-southeast-2
```

Do not destroy bootstrap or ECR roots, delete the state bucket, delete release images or manually remove state/lock objects. Dev destroy removes its seven-day log group, so export any needed evidence first after approval. Audit remaining task ENIs/public IPv4, log storage, ECR images, S3 versions and credit balance. Service-linked roles may persist after teardown and have no direct hourly charge.

## Decision

No confirmed technical blocker to a short approved demonstration remains. Conditions: explicitly approve cost and HTTP-only exposure; narrow ingress if needed and replan; confirm automatic service-linked-role creation is acceptable; ensure no concurrent Terraform execution; recheck image scan, credits and AWS session immediately before a fresh locked plan/apply. IAM simulation and successful planning do not prove runtime provisioning capacity or every effective permission. There is no existing deployment to roll back to on the first launch. **Stop here: deployment is not executed or authorized by this report.**
