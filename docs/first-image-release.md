# First image release preparation — Task 15

Built and tested locally on 5 November 2026. No ECR login/push, Terraform apply/destroy,
AWS resource creation, state modification, credential change or Git push occurred.

## Artifact and actual results

- Local image: `rdp-release:git-24c67e6e52e8-dirty-20261105T160350Z`
- Release tag: `git-24c67e6e52e8-dirty-20261105T160350Z`
- Git revision: `24c67e6e52e86ae975e7136b8300e0d77d24bb16`
- Architecture: linux/amd64; user: 10001:10001; runtime Python: 3.12.16.
- Local image size: 295,940,018 bytes (not the compressed ECR storage size).
- Tests: 16 passed, 2 opt-in PostgreSQL/Compose integration tests skipped.
- Ruff: passed. Host tests ran under Python 3.15.2; image HTTP checks ran under 3.12.16.
- One host dependency deprecation warning; no test failure.
- /health, /ready, /version, /metrics: HTTP 200, response contents checked.
- Container test: no network access, empty DATABASE_URL/DATABASE_PASSWORD_FILE,
  0.25 CPU and 512 MiB memory limits. No traceback in inspected logs.
- Test container stopped and automatically removed. No Compose volumes were touched.

Docker Desktop was initially stopped; starting the installed engine succeeded.
The existing multi-stage Dockerfile built with --platform linux/amd64. Its allowlist
build context excludes secrets, .env, state, Git and virtual environments. Existing
non-root Uvicorn command, 0.0.0.0 binding and port 8000 match the ECS configuration.

README.md was modified before this build, so the packaged README does not match HEAD.
The tag explicitly includes dirty; no claim is made that this is a clean-commit
artifact. The exact context hash and image ID are in [release evidence](../evidence/task15-release.json).
App/Dockerfile/pyproject sources had no tracked changes at build time. Dependencies
are version ranges and base image is a moving tag; rebuilding can produce a different
artifact. A clean committed release requires a new build/tag and checks, not relabeling
this image as clean. No commit or Git push was made.

APP_VERSION and GIT_SHA are runtime configuration. Tests injected the release tag and
revision; a later ECS plan must set those variables explicitly. /ready in this mode
does not validate a PostgreSQL dependency. Short smoke checks do not prove load capacity.

## Exact push commands — approval required, not executed

The ECR root output was read privately and matched AWS DescribeRepositories for
aws-resilient-delivery-platform-dev in Sydney. Repository tags are IMMUTABLE.
No account ID or repository URL is included in this document.

Run from the repository root after approval to upload this dirty-context candidate
(or rebuild from a reviewed clean revision instead). Ensure the existing profile is
current and competing static credential environment variables are absent. These
commands check the recorded local image before tagging it; never rebuild this tag.

```powershell
$env:AWS_PROFILE = 'rdp-dev'
$env:AWS_REGION = 'ap-southeast-2'
$env:AWS_DEFAULT_REGION = 'ap-southeast-2'
$release = Get-Content evidence/task15-release.json -Raw | ConvertFrom-Json
$localImage = $release.local_image
$tag = $release.tag
$localId = docker image inspect $localImage --format '{{.Id}}'
if ($LASTEXITCODE -ne 0 -or $localId -ne $release.image_id) { throw 'Local image changed or missing' }
$repoUri = terraform -chdir=infra/envs/ecr output -raw repository_url
if ($LASTEXITCODE -ne 0 -or -not $repoUri) { throw 'ECR output unavailable' }
$repoName = 'aws-resilient-delivery-platform-dev'
$actualUri = aws ecr describe-repositories --profile rdp-dev --region ap-southeast-2 --repository-names $repoName --query 'repositories[0].repositoryUri' --output text
if ($LASTEXITCODE -ne 0 -or $actualUri -ne $repoUri) { throw 'Repository mismatch' }
$registry = ($repoUri -split '/')[0]
$image = "${repoUri}:$tag"
# Check tag absence privately. Only ImageNotFoundException means it is unused;
# AccessDenied, credential or network errors must stop the upload.
aws ecr describe-images --profile rdp-dev --region ap-southeast-2 --repository-name $repoName --image-ids "imageTag=$tag" *> .tools/task15-tag-check.log
if ($LASTEXITCODE -eq 0) { throw 'Immutable tag already exists; do not overwrite' }
if (-not (Select-String -Path .tools/task15-tag-check.log -Pattern 'ImageNotFoundException' -Quiet)) { throw 'Tag check failed; inspect private log' }
aws ecr get-login-password --profile rdp-dev --region ap-southeast-2 | docker login --username AWS --password-stdin $registry
if ($LASTEXITCODE -ne 0) { throw 'ECR login failed' }
docker tag $localImage $image
if ($LASTEXITCODE -ne 0) { throw 'Tag failed' }
docker push $image *> .tools/task15-push.log
if ($LASTEXITCODE -ne 0) { throw 'Push failed; inspect private log' }
```

Password is piped directly to Docker, never printed or written to a script. Push
logs are private/ignored because repository URLs contain account identifiers. Docker
login can store a temporary registry token through the existing Docker credential
helper; log out on completion or failure. Do not change AWS credentials.

## Verify the registry digest after upload

Continue in the same shell only after a successful authorized push:

```powershell
$digest = aws ecr describe-images --profile rdp-dev --region ap-southeast-2 --repository-name $repoName --image-ids "imageTag=$tag" --query 'imageDetails[0].imageDigest' --output text
if ($LASTEXITCODE -ne 0 -or $digest -notmatch '^sha256:[a-f0-9]{64}$') { throw 'ECR digest unavailable' }
$pushLog = Get-Content .tools/task15-push.log -Raw
$match = [regex]::Match($pushLog, 'digest:\s+(sha256:[a-f0-9]{64})')
if (-not $match.Success -or $match.Groups[1].Value -ne $digest) { throw 'Push/ECR digest mismatch; investigate' }
$digestImage = "${repoUri}@$digest"
docker logout $registry
```

Use $digestImage privately as the later ECS container_image value. Do not assume a
local image ID always equals the registry manifest/index digest. Review ECR scan
status/findings separately: scan-on-push is not an automatic vulnerability gate.
Repository supports immutability; local Docker tags remain technically movable.

## Safe cleanup

The temporary test container has already been removed. Retain the verified local
image until upload/digest verification or a deliberate decision to discard it.
When no longer needed, `docker image rm $localImage` removes this named local tag;
if the ECR URI was tagged locally, remove that exact local tag separately with
`docker image rm $image`. Confirm neither is needed by a running container; do not
force deletion. Avoid system prune, volume prune and Compose down -v.

Remote image deletion needs separate approval. First verify no task or rollback uses
the digest, then delete only that reviewed ECR image digest. Do not delete the repository,
state bucket or Terraform records as image cleanup. The 20-image lifecycle policy
can expire older images automatically, so protect rollback requirements deliberately.

## Next milestone

Approve this candidate's provenance or build a new clean-commit candidate, then
authorize ECR login/push. Only after digest/scan verification should a separate ECS
and ALB plan be reviewed. No deployment approval is implied by these local checks.
