# Manual ECR release using temporary CLI credentials

This is a future, explicitly approved human release procedure. Task34 does not
execute it. OIDC publishing stays disabled; do not bypass the GitHub-only guards
in `scripts/release_image.py publish`. The existing ECR repository must already
exist. No IAM, infrastructure, account-plan or permanent credential changes are
part of publishing an image.

Use a private PowerShell terminal, Docker Linux engine, repository virtual
environment and the existing rdp-dev login. Do not print credentials, enable debug
output, use a shared transcript, or copy ignored logs/auth configuration into Git.
Stop on any failure. Never overwrite a previous immutable tag or retry a push
blindly when it may already have succeeded.

## 1. Review and build the exact release

Require a clean reviewed commit, a passing hosted CI run for that commit and
explicit release approval. Task34's later local docs commit has no hosted CI until
an authorized push/PR; the run for 693efb2 is not proof for a different commit.

```powershell
if (git status --porcelain) { throw 'Commit/review source before releasing' }
$releaseSha = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $releaseSha -notmatch '^[a-f0-9]{40}$') { throw 'Invalid source commit' }
$tag = 'git-' + $releaseSha.Substring(0, 12)
python -m pytest -m 'not integration'
if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed' }
python -m ruff check .
if ($LASTEXITCODE -ne 0) { throw 'Ruff failed' }
# Run the CI PostgreSQL16 integration gate as well; use the existing local/CI
# service procedure rather than pointing tests at production data.
python scripts/release_image.py build --local-validate
if ($LASTEXITCODE -ne 0) { throw 'AMD64 build, complete Trivy scan or runtime checks failed' }
$build = Get-Content .tools/release/build.json -Raw | ConvertFrom-Json
if ($build.revision -ne $releaseSha -or $build.tag -ne $tag -or !$build.scan_passed -or !$build.runtime_passed) { throw 'Build evidence mismatch' }
if (git status --porcelain) { throw 'Source changed during verification' }
if ((git rev-parse HEAD).Trim() -ne $releaseSha) { throw 'Commit changed during verification' }
```

The helper builds linux/amd64, verifies UID10001, scans OS/Python inventories
including unfixed findings, rejects HIGH/CRITICAL and tests /health, /ready,
/version and /metrics without PostgreSQL. It records the source, recipe/config
digest and image archive checksum under ignored `.tools/release/`. The local-only
marker prevents promotion through the GitHub `publish` command; do not remove it.
The actual human push below is separate. Recheck scan databases for each release.

## 2. Authenticate temporarily and reject tag collisions

`aws login` is an interactive user action if the existing session has expired.
Do not create access keys or activate advanced features to work around expiry.
Use only an approved session with ECR push permissions; existing permissions may
be broader than the future dedicated OIDC role and must not be described as that
least-privilege role. No long-lived credential values are stored by this procedure.

```powershell
$region = 'ap-southeast-2'
$profile = 'rdp-dev'
$repoName = 'aws-resilient-delivery-platform-dev'
New-Item -ItemType Directory -Force .tools/manual-release | Out-Null
if ((Test-Path Env:AWS_ACCESS_KEY_ID) -or (Test-Path Env:AWS_SECRET_ACCESS_KEY)) { throw 'Review environment credential overrides first; do not print them' }
$credentialCheck = aws configure export-credentials --profile $profile --format process | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Temporary login unavailable; authenticate interactively and restart review' }
if (!$credentialCheck.SessionToken -or !$credentialCheck.Expiration -or $credentialCheck.AccessKeyId.StartsWith('AKIA')) { throw 'Require an expiring temporary session' }
if ([DateTimeOffset]::Parse($credentialCheck.Expiration) -le [DateTimeOffset]::UtcNow.AddMinutes(20)) { throw 'Insufficient session time; authenticate and restart' }
Remove-Variable credentialCheck
$repo = aws ecr describe-repositories --repository-names $repoName --profile $profile --region $region --output json 2> .tools/manual-release/aws-error-private.log | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Existing repository lookup failed' }
$repo = $repo.repositories[0]
if ($repo.imageTagMutability -ne 'IMMUTABLE' -or !$repo.imageScanningConfiguration.scanOnPush) { throw 'Repository security policy mismatch' }
$callerAccount = aws sts get-caller-identity --profile $profile --region $region --query Account --output text
if ($LASTEXITCODE -ne 0 -or $repo.registryId -ne $callerAccount.Trim()) { throw 'AWS account mismatch' }
$repoUri = $repo.repositoryUri
$registry = $repoUri.Split('/')[0]
$remoteImage = "${repoUri}:$tag"
aws ecr describe-images --repository-name $repoName --image-ids "imageTag=$tag" --profile $profile --region $region --output json > .tools/manual-release/tag-private.json 2> .tools/manual-release/tag-error-private.log
if ($LASTEXITCODE -eq 0) { throw 'Immutable tag already exists; inspect read-only instead of pushing' }
if ((Get-Content .tools/manual-release/tag-error-private.log -Raw) -notmatch '\(ImageNotFoundException\)') { throw 'Collision check failed; absence not established' }
```

Captured identity/repository values are private variables, never shared logs.
The only acceptable missing-tag response is ImageNotFoundException; denied access
or network errors must not be mistaken for an available tag.

## 3. Approved push with isolated Docker authentication

This avoids the Windows credential-helper failure by using a new empty Docker
configuration scoped to this operation. The temporary registry token may be
stored in its config until final cleanup; it is ignored and must stay private.
No system Docker credential helper is changed. Do not use cmd/string interpolation.

```powershell
if ((Get-FileHash .tools/release/image.tar -Algorithm SHA256).Hash.ToLowerInvariant() -ne $build.archive_sha256) { throw 'Scanned archive changed' }
$localImage = $build.image
docker load -i .tools/release/image.tar *> .tools/manual-release/load-private.log
if ($LASTEXITCODE -ne 0) { throw 'Exact archive reload failed' }
$runtime = docker image inspect $localImage --format '{{.Os}}/{{.Architecture}} {{.Config.User}}'
if ($LASTEXITCODE -ne 0 -or $runtime -ne 'linux/amd64 10001:10001') { throw 'Wrong runtime architecture/user' }
docker tag $localImage $remoteImage
if ($LASTEXITCODE -ne 0) { throw 'Local tag failed' }
$authRoot = [IO.Path]::GetFullPath((Join-Path (Get-Location) '.tools/manual-release'))
$dockerConfig = Join-Path $authRoot ('auth-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $dockerConfig -ErrorAction Stop | Out-Null
Set-Content -LiteralPath (Join-Path $dockerConfig 'config.json') -Value '{}' -Encoding Ascii
try {
    $password = aws ecr get-login-password --profile $profile --region $region
    if ($LASTEXITCODE -ne 0) { throw 'ECR authentication failed; no push attempted' }
    $password | docker --config $dockerConfig login --username AWS --password-stdin $registry *> .tools/manual-release/login-private.log
    $password = $null
    if ($LASTEXITCODE -ne 0) { throw 'Docker login failed' }
    if (git status --porcelain) { throw 'Source became dirty; no push' }
    if ((git rev-parse HEAD).Trim() -ne $releaseSha) { throw 'Commit changed; no push' }
    # This is the explicitly approved publishing operation, never automatic:
    docker --config $dockerConfig push $remoteImage *> .tools/manual-release/push-private.log
    if ($LASTEXITCODE -ne 0) { throw 'Push may have partially/completely succeeded; inspect ECR before any retry' }
} finally {
    $password = $null
    docker --config $dockerConfig logout $registry *> .tools/manual-release/logout-private.log
    $resolvedAuth = [IO.Path]::GetFullPath($dockerConfig)
    if (!$resolvedAuth.StartsWith($authRoot + [IO.Path]::DirectorySeparatorChar) -or (Split-Path $resolvedAuth -Leaf) -notmatch '^auth-[a-f0-9]{32}$') { throw 'Unsafe auth cleanup path; inspect privately' }
    Remove-Item -LiteralPath $resolvedAuth -Recurse -Force
}
```

Use one operator/terminal; do not retag the local image concurrently. Scan/runtime
failure or an incomplete push is not a verified release. A failed operation does
not authorize deleting a tag. If logout/removal fails, treat the isolated config
as sensitive and remove only that known owned directory after inspection.

## 4. Bind remote content and complete the ECR scan

```powershell
$rootDigest = aws ecr describe-images --repository-name $repoName --image-ids "imageTag=$tag" --profile $profile --region $region --query 'imageDetails[0].imageDigest' --output text
if ($LASTEXITCODE -ne 0 -or $rootDigest -notmatch '^sha256:[a-f0-9]{64}$') { throw 'Remote digest unverified' }
$pushDigests = [regex]::Matches((Get-Content .tools/manual-release/push-private.log -Raw), 'digest:\s+(sha256:[a-f0-9]{64})') | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
if (@($pushDigests).Count -ne 1 -or $pushDigests -ne $rootDigest) { throw 'Push/registry digest mismatch' }
$savedProfile = $env:AWS_PROFILE
try {
    $env:AWS_PROFILE = $profile
    # Read-only helper: hash manifest bytes, resolve exactly one AMD64 child,
    # and compare its config with the scanned archive's recorded config digest.
    $childDigest = python -c "import sys;sys.path.insert(0,'scripts');from release_image import verify_remote;print(verify_remote(sys.argv[1],sys.argv[2]))" $rootDigest $build.config_digest
    if ($LASTEXITCODE -ne 0) { throw 'Remote content differs or is ambiguous' }
} finally { $env:AWS_PROFILE = $savedProfile }
$scanComplete = $false
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    aws ecr describe-image-scan-findings --repository-name $repoName --image-id "imageDigest=$childDigest" --profile $profile --region $region --output json > .tools/manual-release/scan-private.json 2> .tools/manual-release/scan-error-private.log
    if ($LASTEXITCODE -ne 0) { throw 'Scan unavailable; published image remains unverified' }
    $scan = Get-Content .tools/manual-release/scan-private.json -Raw | ConvertFrom-Json
    if ($scan.imageScanStatus.status -eq 'COMPLETE') { $scanComplete = $true; break }
    if ($scan.imageScanStatus.status -notin @('PENDING','IN_PROGRESS')) { throw 'ECR scan failed; image not approved' }
    Start-Sleep -Seconds 5
}
if (!$scanComplete) { throw 'Scan timed out; image exists but is not approved' }
$counts = $scan.imageScanFindings.findingSeverityCounts
@{ commit=$releaseSha; tag=$tag; repository=$repoName; region=$region; root_digest=$rootDigest; amd64_digest=$childDigest; config_digest=$build.config_digest; scan_status='COMPLETE'; severity_counts=$counts; deployment_executed=$false } | ConvertTo-Json -Depth 8 | Set-Content .tools/manual-release/verification.json -Encoding Ascii
if ($counts.HIGH -gt 0 -or $counts.CRITICAL -gt 0) { throw 'HIGH/CRITICAL findings: do not deploy; retain all findings for review' }
```

Scan the AMD64 child, not an OCI index. Index digest, child manifest digest and
local config digest are different identities. A successful ECR scan may differ
from Trivy; preserve every finding, including unfixed/lower-severity findings.
Inspect the raw scan privately and sanitize package/CVE data before sharing.
Release evidence must be reviewed before Git inclusion; no registry/account IDs,
token files, image tar, environment dump or raw logs are portfolio artifacts.

## Cleanup and limits

Logout/removal above clears only the operation's local Docker authentication
directory; do not delete AWS login caches or change credentials automatically.
ECR registry credentials have a separate lifetime from the CLI session, so keep
them private throughout and do not rely on temporary login alone for revocation.
Remove only reviewed local image tags when no longer needed; avoid system/volume
prune and `docker compose down -v`. Remote image deletion or repository changes
need separate approval; retain any image used by a deployment/rollback.

No ECS/ALB deployment follows a successful manual image release. Preparing or
publishing an image does not authorize infrastructure changes, account upgrades,
or changing Terraform state. This updated runbook was syntax-reviewed, not executed
end-to-end by Task34; it builds on the previously verified manual ECR release.
