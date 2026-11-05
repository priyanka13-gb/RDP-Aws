# ECR deployment plan — Task 12

Historical procedure: Task 14 replaces targeted dev deployment with the
[isolated ECR root](../infra/envs/ecr/README.md). Use that root for future deployment.

Prepared only. No live Terraform plan/apply/destroy, backend reconfiguration, AWS
resource creation, ECR login or image push was performed. Application code is unchanged.

## Findings and verification

The existing ECR module creates an IMMUTABLE repository, AES256 encryption,
scan-on-push configuration and a lifecycle policy retaining the latest 20 images.
force_delete=false prevents Terraform deleting a populated repository. The lifecycle
rule covers all images: older releases used for rollback can eventually expire.
This is not a release-retention guarantee.

Read-only authentication with rdp-dev succeeded. ECR DescribeRepositories returned
RepositoryNotFoundException for aws-resilient-delivery-platform-dev in Sydney.
The expected S3 dev state and lock HeadObject calls returned 404.

Cached backend metadata confirms S3, the expected bucket/key, encryption and native
locking. **Cached region and profile are null**, while ignored backend.hcl explicitly
specifies ap-southeast-2 and rdp-dev. This may reflect environment-based initialization,
not a different bucket, but configuration/cache consistency must be resolved before
planning. No cache or state was changed. See [sanitized evidence](../evidence/ecr-preparation.json).

Terraform formatting and dev validation passed. Local TestClient requests with empty
DATABASE_URL and DATABASE_PASSWORD_FILE returned 200 for /health, /ready, /version and
/metrics. Lifespan skips database-engine creation without DATABASE_URL. A dependency
deprecation warning was emitted; the checks still passed. This is a Python runtime
check, not a container verification.

Dockerfile review confirms Python 3.12 slim, wheel-builder/runtime stages, UID/GID
10001, exec-form Uvicorn on 0.0.0.0:8000 and no Compose mounts required. .dockerignore
allows only packaging metadata and application source. Explicit linux/amd64 matches
the ECS X86_64 task configuration. Actual build attempt failed: Docker Desktop Linux
engine pipe dockerDesktopLinuxEngine was absent. Initial sandbox restrictions were
also encountered; an elevated retry confirmed the missing engine. No image was built.
Docker build/runtime verification remains a blocker before upload.

## ECR-only strategy

A normal full dev apply, once required image variables are supplied, creates network,
ECR, observability, IAM, ALB and ECS modules. desired_count=0 stops task launches but
still creates the other resources, including a billable ALB. Do not use full apply
for this ECR-only step.

Recommended exception: a **one-time -target=module.ecr saved plan** to create the
image destination before deploying its consumers. Dependency review:

- ECR inputs are local name/tags derived from variables; no VPC, IAM, ALB or ECS inputs.
- Lifecycle policy depends only on its ECR repository.
- IAM and ECS consume ECR outputs; they are downstream and need not be created first.
- The expected plan is exactly two creates, no updates/deletes:
  module.ecr.aws_ecr_repository.this and module.ecr.aws_ecr_lifecycle_policy.this.

No Terraform source changes are required. This preserves the existing module addresses
and dev state ownership without a new stack, imports or state moves. Targeting is an
exception for this repository bootstrap, not the normal deployment workflow. Review
the actual saved plan: stop if anything beyond those two creates appears. Run a full
plan after the image exists, but do not apply the rest of dev without separate approval.
[HashiCorp targeting guidance](https://developer.hashicorp.com/terraform/cli/commands/plan#resource-targeting).

## Future commands — not executed

Use PowerShell at the repository root and current short-lived profile credentials.
Resolve any competing environment credentials without modifying saved AWS credentials.
Never print tokens, raw identity output or account-specific plan output in shared logs.

```powershell
$env:AWS_PROFILE = 'rdp-dev'
$env:AWS_REGION = 'ap-southeast-2'
$env:AWS_DEFAULT_REGION = 'ap-southeast-2'
$repoName = 'aws-resilient-delivery-platform-dev'
$gitSha = (git rev-parse HEAD).Trim()
if (git status --porcelain) { throw 'Review and commit the intended release locally before release tagging; no Git push required.' }
$tag = 'git-' + $gitSha + '-' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$localImage = 'rdp-release:' + $tag
```

Current working tree has uncommitted infrastructure/documentation changes. Do not
label an unreviewed dirty build as exactly matching HEAD. No commit was made here.

1. Recheck both configured and cached backend locations, local state and remote
   versions/locks. If they still match this empty dev backend, an approved
   `terraform -chdir=infra/envs/dev init -reconfigure -backend-config=backend.hcl
   -input=false` (one line) can record the explicit region/profile without migration.
   Stop on any unexpected state or migration prompt; never use -migrate-state or
   -force-copy. This cache correction is proposed, not performed.
2. Prepare a plan only when authorized for backend locking (plan can create/delete
   a temporary S3 lock object). Capture the account-specific URI privately:

```powershell
$account = aws sts get-caller-identity --profile rdp-dev --region ap-southeast-2 --query Account --output text
if ($LASTEXITCODE -ne 0) { throw 'Identity lookup failed' }
$registry = "$account.dkr.ecr.ap-southeast-2.amazonaws.com"
$repoUri = "$registry/$repoName"
$image = "${repoUri}:$tag"
terraform -chdir=infra/envs/dev plan -input=false -target=module.ecr -var='aws_region=ap-southeast-2' -var="container_image=$image" -var='desired_count=0' -out=ecr-bootstrap.tfplan
if ($LASTEXITCODE -ne 0) { throw 'Plan failed' }
```

Review privately and approve only the exact two-resource plan. The eventual apply
command requiring explicit resource-creation approval is:

```powershell
terraform -chdir=infra/envs/dev apply ecr-bootstrap.tfplan
```

3. Start Docker Desktop's Linux engine and verify it. Build/test locally before any
   image upload; these commands themselves do not contact ECR or create AWS resources:

```powershell
docker info
docker build --platform linux/amd64 -f app/Dockerfile -t $localImage .
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
docker image inspect $localImage --format '{{.Os}}/{{.Architecture}} {{.Config.User}}'
# Expected: linux/amd64 10001:10001
$container = docker run -d --rm -p 127.0.0.1::8000 -e DATABASE_URL= -e DATABASE_PASSWORD_FILE= -e "APP_VERSION=$tag" -e "GIT_SHA=$gitSha" $localImage
if ($LASTEXITCODE -ne 0) { throw 'Container start failed' }
docker port $container 8000
# Use the assigned localhost port; wait for startup and check /health, /ready,
# /version and /metrics for HTTP 200. Inspect docker logs $container.
docker stop $container
```

Use only this temporary container ID for cleanup; preserve Compose containers and
PostgreSQL volumes. Prefer the verified image digest for the later ECS deployment.

4. After separate approval to authenticate Docker and push the image, confirm the
   repository URI matches the intended account/region, then execute:

```powershell
$actualUri = aws ecr describe-repositories --repository-names $repoName --profile rdp-dev --region ap-southeast-2 --query 'repositories[0].repositoryUri' --output text
if ($LASTEXITCODE -ne 0 -or $actualUri -ne $repoUri) { throw 'Unexpected repository' }
aws ecr get-login-password --profile rdp-dev --region ap-southeast-2 | docker login --username AWS --password-stdin $registry
if ($LASTEXITCODE -ne 0) { throw 'ECR login failed' }
docker tag $localImage $image
if ($LASTEXITCODE -ne 0) { throw 'Tag failed' }
docker push $image
if ($LASTEXITCODE -ne 0) { throw 'Push failed' }
$digest = aws ecr describe-images --repository-name $repoName --image-ids "imageTag=$tag" --profile rdp-dev --region ap-southeast-2 --query 'imageDetails[0].imageDigest' --output text
if ($LASTEXITCODE -ne 0) { throw 'Digest lookup failed' }
docker logout $registry
```

Docker push output contains the repository URI; keep it private. Password goes
directly to stdin, never a file or command argument. Review scan status/findings;
scan-on-push is not itself a vulnerability gate. Record $repoUri + '@' + $digest
privately for container_image. Do not overwrite an immutable tag or use latest.

## Permissions

Push identity needs ecr:GetAuthorizationToken on '*'; scope BatchCheckLayerAvailability,
InitiateLayerUpload, UploadLayerPart, CompleteLayerUpload, PutImage and BatchGetImage
to this repository. DescribeRepositories, DescribeImages and DescribeImageScanFindings
support verification. [AWS push policy](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-push-iam.html).

Terraform additionally needs repository creation/read/tagging, lifecycle-policy
write/read and necessary repository-setting actions, plus state/lock permissions.
The ECS execution role's pull permissions are not upload permissions. Current
DescribeRepositories access passed (repository not found); create/push and lock-write
permissions were not exercised. Do not create keys or change the account plan.

## Costs and cleanup

ECR-only creates no running compute, ALB, NAT or ECS costs. Main costs are retained
compressed image layers, applicable internet/cross-region transfer, and S3 state
requests/versions. As an illustration at AWS's published $0.10/GB-month storage
example, 0.5 GB is about $0.05/month and 10 GB about $1/month before credits/tax.
Actual Sydney pricing and unique stored layers govern the bill; the build failed,
so actual image size is unknown. Same-region ECR-to-Fargate transfer is free under
the cited pricing. Enhanced scanning, if enabled at registry level, can add charges;
it was not inspected/enabled here. [AWS ECR pricing](https://aws.amazon.com/ecr/pricing/).

The 20-image lifecycle policy limits count, not GB or spend. Before deletion, confirm
no deployed task or required rollback uses the digest. Deleting images is separately
approved and uses BatchDeleteImage scoped to this repository. Emptying it is required
before Terraform deletion because force_delete=false. For an ECR-only state, review
a fresh destruction plan and approve only those two resources; once other modules
are deployed, do not run a full dev destroy merely to remove ECR. Preserve S3 backend
and bootstrap state, and never delete state records to hide resources. No cleanup
or destruction command was executed.

## Remaining blockers

Docker Linux engine unavailable; AMD64 build and container startup unverified.
Cached backend configuration differs from the prepared file and needs deliberate
reconfiguration after repeat state checks. Release source/tag needs review. The ECR
repository, image upload and subsequent infrastructure deployment each still require
approval. No live plan was run, so the two-resource count is expected from dependency
inspection, not a verified AWS plan result.
