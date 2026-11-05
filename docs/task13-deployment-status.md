# Task 13 — deployment verification

Read-only checks on 5 November 2026 used rdp-dev in ap-southeast-2.
No plan, apply, destroy, build, login, push or state mutation was executed.

## What was actually deployed

The root with confirmed deployed resources is **infra/bootstrap**. Its local state
has serial 7 and six managed instances:

1. aws_s3_bucket.state
2. aws_s3_bucket_ownership_controls.state
3. aws_s3_bucket_policy.https_only
4. aws_s3_bucket_public_access_block.state
5. aws_s3_bucket_server_side_encryption_configuration.state
6. aws_s3_bucket_versioning.state

These represent one bucket, rdp-tfstate-sydney-be4bb3dfae, and five settings resources.
Live S3 checks confirm the bucket and its settings. Bootstrap outputs contain that
bucket name and its S3 ARN. Bootstrap state remains local and was not modified.

Dev state pull succeeded but returned serial 0, **zero managed resources and zero
outputs**. Thus there is no ECR URL, ALB URL or ECS service output to use. An empty
state returned by Terraform does not by itself prove that an S3 state object exists.
The separate object existence check is recorded in the evidence.

This identifies bootstrap as the deployed root; it cannot prove which command was
most recently run. A dev no-op/failed apply, another workspace/account/region, or an
apply from another checkout cannot be inferred from these results. Do not rerun apply
blindly if the previous terminal reported successful ECR/ECS creation; reconcile that
terminal's root, profile, region and workspace first. No cross-account search was done.

| Live check | Result |
| --- | --- |
| Expected ECR repository aws-resilient-delivery-platform-dev | RepositoryNotFoundException |
| Images in expected repository | Cannot exist there while repository is absent |
| ECS clusters in Sydney | None |
| Load balancers in Sydney | None |
| IAM roles matching project environment name | None |
| VPCs | One pre-existing default VPC, 172.31.0.0/16; no project VPC |
| Subnets tagged with project | None |
| NAT gateways / allocated Elastic IPs in Sydney | None / zero |
| Project ECS log groups | None |
| Free plan | Active; USD 120 remaining credit reported |

This is project/Sydney verification, not an exhaustive global billing audit.
See [sanitized live/state evidence](../evidence/task13-deployment-verification.json).

## Backend and next milestone

Dev cache selects the correct bucket and dedicated key, encrypt=true and
use_lockfile=true. Cached region/profile are null; the prepared backend.hcl explicitly
selects Sydney/rdp-dev. State pull used explicit environment/profile settings and
succeeded. Before a future plan, deliberately resolve the cache/file discrepancy
using the [Task 12 procedure](ecr-deployment-plan.md); do not migrate state.

The next milestone is **create and verify ECR only**, then build/test/upload a release,
then separately review a complete ECS/network/ALB plan. The existing ECR-only plan
documents the justified one-time target and expected two-resource scope. A normal
full dev apply creates networking, IAM, logs, ALB and ECS as well. No such apply is
authorized by this review.

## Exact image commands for later approval

These commands are **not to be run yet**. They require an approved, existing ECR
repository and a reviewed clean Git revision. Current working tree has uncommitted
changes. The missing repository is a prerequisite, not an empty-registry success.
No Git commit or push was made here. Use PowerShell from the repository root:

```powershell
$env:AWS_PROFILE = 'rdp-dev'
$env:AWS_REGION = 'ap-southeast-2'
$env:AWS_DEFAULT_REGION = 'ap-southeast-2'
if (git status --porcelain) { throw 'Review and commit release changes locally before building.' }
$sha = (git rev-parse HEAD).Trim()
$tag = 'git-' + $sha + '-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$localImage = 'rdp-release:' + $tag
$repoName = 'aws-resilient-delivery-platform-dev'
$repoUri = aws ecr describe-repositories --profile rdp-dev --region ap-southeast-2 --repository-names $repoName --query 'repositories[0].repositoryUri' --output text
if ($LASTEXITCODE -ne 0 -or -not $repoUri) { throw 'Repository not available; stop.' }
$registry = ($repoUri -split '/')[0]
$image = "${repoUri}:$tag"
docker info
if ($LASTEXITCODE -ne 0) { throw 'Docker Linux engine unavailable' }
docker build --platform linux/amd64 -f app/Dockerfile -t $localImage .
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
docker image inspect $localImage --format '{{.Os}}/{{.Architecture}} {{.Config.User}}'
# Required: linux/amd64 10001:10001
```

Before upload, run the temporary-container checks in Task 12: /health, /ready,
/version and /metrics must pass with database settings empty. Confirm release
metadata, inspect logs and stop only the temporary test container. The previous
build attempt was blocked by an unavailable Docker Linux engine; its availability
was not retested in this verification-only task.

Only after upload authorization, pipe the login password directly to Docker:

```powershell
aws ecr get-login-password --profile rdp-dev --region ap-southeast-2 | docker login --username AWS --password-stdin $registry
if ($LASTEXITCODE -ne 0) { throw 'Login failed' }
docker tag $localImage $image
if ($LASTEXITCODE -ne 0) { throw 'Tag failed' }
docker push $image
if ($LASTEXITCODE -ne 0) { throw 'Push failed' }
$digest = aws ecr describe-images --profile rdp-dev --region ap-southeast-2 --repository-name $repoName --image-ids "imageTag=$tag" --query 'imageDetails[0].imageDigest' --output text
if ($LASTEXITCODE -ne 0) { throw 'Digest verification failed' }
docker logout $registry
```

Keep account-specific URI output private. Never display/store the login password.
Use the resulting digest URI for later container_image and inspect scan results.
Repository configuration is IMMUTABLE; never reuse/overwrite a tag or use latest.
Git SHA plus timestamp identifies a release build; dependencies/base image are not
locked, so digest remains the strongest identity for the actual built artifact.

## Compatibility, security and cost

There is no deployed project ECS task definition confirmed by dev state. The configured
definition requires Linux X86_64, UID/GID 10001, port 8000, 0.25 vCPU and 0.5 GiB RAM.
Dockerfile matches architecture when explicitly built for linux/amd64, user and port;
it runs Uvicorn on 0.0.0.0 and needs no Compose mounts. DATABASE_URL is empty in ECS,
so application lifespan skips PostgreSQL and /ready is application-only readiness.
Runtime under the Fargate memory limit has not been verified.

Current confirmed project cost exposure is S3 storage, retained versions and requests.
No project ECR storage, ECS task, ALB or NAT running cost was observed. A default VPC
does not establish that unrelated compute is absent; this is not a zero-bill claim.
No Cost Explorer billing query was run and credit balance is not actual spend.

After ECR upload, storage and applicable transfer become relevant: AWS's published
example rate of $0.10/GB-month implies approximately $0.05/month for 0.5 GB before
credits/tax; verify Sydney rates and actual stored layers. Same-region ECR/Fargate
transfer is free under the cited pricing. [AWS ECR pricing](https://aws.amazon.com/ecr/pricing/).
The 20-image lifecycle policy is not a dollar cap and can expire rollback images.

Future ECS/ALB introduces compute, load-balancer and public IPv4 charges even with
cost_saver networking. An ALB can incur usage with zero tasks. The configured ALB
uses HTTP only: keep sensitive traffic out until TLS is implemented. No secrets
belong in image layers, tags or Terraform variables. Keep bootstrap backups and
remote state private; do not delete state or resources as part of verification.
