# First AWS deployment procedure

Task 14 update: ECR now has an [isolated root](../infra/envs/ecr/README.md). Follow
that root's plan/apply procedure before the image build/upload and dev deployment.
The zero-task full-dev staging procedure below is historical and must not be used
to create ECR: dev now reads an existing repository instead of managing it.

This is a future runbook, not deployment authorization. Task 8 performed read-only
checks only. Obtain approval for the reviewed plans and image upload before any
resource changes. See [actual readiness results](../evidence/aws-deployment-readiness.md).

## 1. Confirm identity, tools and settings

Use the existing short-lived `rdp-dev` profile and Sydney region. In the deployment
shell, select AWS_PROFILE=rdp-dev and AWS_REGION=ap-southeast-2. Check that ambient
credential variables do not select a different identity. Do not print credentials,
identity JSON or account IDs in shared output. Refresh the existing login if expired.

Use the repository's tested Terraform version and committed provider locks. Run
fmt check, init -backend=false, validate and the mock tests for bootstrap/dev/network.
Recheck credits, quotas and the chosen region immediately before deployment.

## 2. Select and protect the state location

Copy infra/bootstrap/terraform.tfvars.example to ignored terraform.tfvars. Set a
globally unique bucket name using a project prefix and random suffix; keep Sydney.
Check the proposed name with read-only S3 calls. Do not adopt another owner's bucket
or interpret AccessDenied as absence. A successful name check cannot reserve a name.

Inventory local state, backups and any prior backend configuration again. If state
exists, stop and identify its owner/resources. Do not use migration flags or overwrite
state. Bootstrap state stays local and requires a secure backup outside Git.

Generate and review a bootstrap plan, stored in an ignored .tfplan file. Check that
it creates only the expected state bucket and its protection settings. After explicit
approval, apply that reviewed plan. Privately back up bootstrap state immediately.

## 3. Initialize a new dev backend

After bootstrap, copy infra/envs/dev/backend.hcl.example to ignored backend.hcl.
Use the actual bucket, Sydney and `aws-resilient-delivery-platform/dev/terraform.tfstate`.
Verify bucket ownership/location, versioning, encryption and public-access blocking.
Use HeadObject and ListObjectVersions to check the exact state key and .tflock key,
including historical versions/delete markers. Resolve any existing state or active
lock; never delete it to make initialization succeed.

Only for a confirmed new backend, initialize with:

```powershell
terraform -chdir=infra/envs/dev init -backend-config=backend.hcl
```

Stop if initialization asks to copy/migrate state. Use the default workspace. Keep
state, plans, backend caches and account-specific outputs private and out of Git.

## 4. Create the image destination without launching tasks

Copy the dev variable example to ignored terraform.tfvars. Keep cost_saver,
nat_gateway_mode=none, enable_rds=false and enable_ssm_parameters=false. Set
desired_count=0 for this initial stage. Supply the intended full Sydney ECR URI
with a unique release tag, deriving the account-specific part privately. Even at
zero tasks the URI must match this stack's repository; never leave placeholders.

Plan the full dev root (avoid ad hoc resource targeting). Review network, ECR, roles,
ALB, logs and zero-task ECS service, and verify zero NAT gateways/EIPs. Approve the
plan before applying. ALB and its public IPs incur usage even with zero tasks.

## 5. Build and publish the release

Run application tests/Ruff and Docker checks. Build app/Dockerfile from the repository
root for linux/amd64, preserving its non-root Uvicorn startup. Confirm .dockerignore
excludes secrets, .env, local environments, Git and caches. Locally test /health,
/ready, /version and /metrics. Ensure cloud startup needs no Compose mounts or db host.

After separate image-push authorization, authenticate Docker to the new repository
using a piped ECR login password (never print/store it). Push a unique immutable tag,
review scan findings, and record its digest. Update container_image to the verified
tag or digest, app_version and git_sha. Never reuse an immutable release tag.

## 6. Start and verify the service

Set desired_count=1, create a fresh full dev plan, review and approve it, then apply
that saved plan. Check service events, stopped-task reasons and CloudWatch logs for
image pull, IAM, startup and health failures. Allow deployment rollback to report
failures; do not weaken security groups to bypass them.

Wait for ECS stability and healthy ALB targets. Through the ALB verify /health and
/ready return 200, /version matches the release, and /metrics is Prometheus output.
Task port 8000 must remain ALB-only. No PostgreSQL is deployed: /ready currently
checks application readiness without a database. Use only non-sensitive HTTP traffic.

## Required deployment permissions

The readiness simulation sampled 32 actions; it is not an exhaustive policy. Before
approval, check the full provider action set against scoped project resources:

| Area | Required capabilities |
| --- | --- |
| EC2/VPC | Describe; create/tag/modify VPC and subnets; Internet Gateway attach; routes and associations; SG rule authorize/revoke; corresponding teardown operations |
| ECS | Cluster, task definition and service create/read/update/delete or deregister; tagging |
| ECR | Repository create/read/tag; lifecycle, scan and immutability configuration; later approved upload actions and authorization token |
| IAM | Project roles and inline policies; tagging/trust configuration; PassRole restricted to the two ECS roles; service-linked role creation restricted to ECS/ELB |
| ELB | ALB, target group and listener management; attributes, tags and describe operations |
| CloudWatch Logs | Group create/read/tag, retention and teardown; runtime stream creation and writes belong on the execution role |
| S3 bootstrap | Bucket creation, region/read, tags, ownership, public-access block, encryption, versioning and policy configuration |
| S3 backend | ListBucket scoped to state prefix; GetObject/PutObject on state; GetObject/PutObject/DeleteObject on .tflock |

The application role must not receive deployment or state access. SSM is disabled;
enabling it later requires existing parameter ARNs, scoped execution-role reads and
optional customer-key decrypt permission. No access keys are needed.

Native lockfile permissions are documented by
[HashiCorp](https://developer.hashicorp.com/terraform/language/backend/s3).
Review [teardown and cost audit](teardown-cost-audit.md) before starting the demo.
