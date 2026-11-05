# AWS deployment readiness — 5 November 2026

Result: read-only access checks passed; deployment prerequisites remain. No AWS
resources were created or changed. No apply, destroy, image push, backend
initialization, state migration, account upgrade or Git push was performed.

## Observed results

Profile `rdp-dev`, regional requests `ap-southeast-2`. STS authentication succeeded
using an assumed role. Reports deliberately omit identities, account IDs and secrets.

| Check | Actual result |
| --- | --- |
| EC2/VPC | Read succeeded; 1 existing VPC, none with project CIDR; 1 Internet Gateway |
| Availability zones | Three available standard Sydney AZs; configuration dynamically chooses two |
| ECS | Read succeeded; 0 clusters |
| ECR | Read succeeded; 0 repositories; release repository/image not yet present |
| S3 | Read succeeded; 0 owned buckets |
| IAM | Read succeeded; 10 roles; ECS and ELB service-linked roles absent |
| Elastic Load Balancing | Read succeeded; 0 load balancers |
| Project CloudWatch logs | Read succeeded; 0 matching groups |
| Free plan | FREE, ACTIVE; USD 120 remaining credits; reported expiration 5 May 2027 |
| Permission simulation | 32 sampled deployment actions allowed with Sydney request context |
| Local state | No state or state backup files found in inspected repository |
| Local configuration | No bootstrap/dev terraform.tfvars or dev backend.hcl |

Initial simulation without request context produced regional explicit denials.
Repeating with `aws:RequestedRegion`, `s3:LocationConstraint` and
`iam:PassedToService` context allowed all sampled actions. The second result
supersedes those context-free denials. Wildcard-resource simulation is a sample,
not proof of every provider API, actual resource policy, session restriction,
service-linked role creation or service capacity. No create APIs were tested.

Evidence: [initial read-only report](aws-readiness-readonly.json) and
[context-aware simulation and quota report](aws-readiness-refined.json).

## Quota headroom

| Resource | Observed limit | Planned requirement / qualification |
| --- | --- | --- |
| VPCs / Internet Gateways | 5 each; 1 each present | One additional each |
| Subnets per VPC | 200 | Four |
| Security groups per Region / per ENI | 2500 / 5 | Three project groups; one on each task |
| Fargate On-Demand vCPU | 30 | 0.25 steady; up to 0.5 during a one-task rollout |
| ALBs / target groups | 50 / 3000; no LBs present | One each |
| IAM roles | 1000; 10 present | Two project roles, plus missing service-linked roles |
| S3 general-purpose buckets | 10000 | One |
| ECR repositories | 100000 service default | One; account applied value not returned by filtered query |

IAM quota lookup in Sydney returned NoSuchResourceException; the global endpoint
and IAM account summary confirmed the role limit. S3 global quota lookup succeeded.
These are a snapshot, not reserved capacity; total shared Fargate usage outside ECS
was not inventoried. No quota increase was requested.

## Configuration review and remaining blockers

- Bootstrap uses local state and a private, versioned, encrypted S3 bucket protected
  by prevent_destroy and force_destroy=false. Its bucket name is still a placeholder.
- Dev uses the S3 key `resilient-delivery-platform/dev/terraform.tfstate`, Sydney,
  encryption and native lockfiles. No remote backend was initialized.
- No existing state was overwritten. Absence of local state and owned buckets does
  not prove a future selected name/key is safe: confirm ownership, location, current
  object, historical versions and lock object before initializing that backend.
  A 403 is not evidence that a bucket or state object is absent.
- All six dev module references point to existing local modules. VPC CIDR remains
  10.0.0.0/16. cost_saver selects no NAT gateways/EIPs/private default routes.
- ECS uses public subnets and public IPs for ECR/log access; task ingress on 8000
  accepts only the ALB security group. ALB uses HTTP 80 and /ready; container health
  uses /health. Private subnets have no outbound internet in cost_saver.
- Release image must be Linux amd64, explicitly tagged (not latest) or digest-pinned,
  in this environment's Sydney ECR repository. Repository is immutable. Image and
  release metadata must be supplied before starting tasks.
- RDS and SSM parameter injection are disabled. ECS has empty database settings;
  /ready does not prove PostgreSQL connectivity in this deployment. Optional SSM
  support consumes existing parameters; it does not provision them.
- Service-linked roles for ECS and ELB must be allowed to be created during the
  future deployment. The sampled CreateServiceLinkedRole simulation passed.
- HTTP is suitable only for non-sensitive demo traffic; TLS is not implemented.

Terraform configuration was inspected without editing it. The previously reported
validation and 22 mock-plan tests were not rerun as part of this read-only readiness
review; they are not evidence of a successful AWS deployment.

## Free-plan interpretation

AWS lists the required core services in the new experience's supported Free Tier
services. Regional resources must remain in the assigned project region; global
service endpoints can differ. Service availability does not grant every operation.
No observed result establishes a need to upgrade the account.

Credits can be consumed by this architecture. The Free plan ends at six months or
credit exhaustion, whichever comes first; the reported date is not a guarantee
that credits will last until then.

Sources: [supported services](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html),
[project regions](https://docs.aws.amazon.com/accounts/latest/reference/project-regions.html),
[Free plan terms](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier.html).

Next: follow the [first deployment procedure](../docs/first-aws-deployment.md) only
with separate deployment authorization. Keep the
[teardown and cost audit](../docs/teardown-cost-audit.md) available before deployment.
