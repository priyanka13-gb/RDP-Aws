# Manual ECR release - review only, publishing disabled by default

Task29 prepares `.github/workflows/release.yml`; it has **only workflow_dispatch**.
Task 31 reviewed this implementation for a local commit. Nothing was pushed,
provisioned or enabled by this review. No AWS role assumption, Docker login to
ECR, image push or ECS/ALB deployment was executed. The proposed release role
returned NoSuchEntity during the Task 31 read-only check. Hosted CI results,
environment protections and repository enablement settings remain unverified.

## Workflow and gate design

1. Request guard requires this repository, refs/heads/main and manual dispatch.
   Input `publish` defaults to false. A request with publish=true is rejected unless
   repository variable `ECR_RELEASE_PUBLISH_APPROVED` is exactly `true`.
2. The existing CI workflow is called as the mandatory test/security gate. Its only
   change is adding workflow_call support; PR/main checks remain unchanged. Ruff,
   Python/PostgreSQL tests, isolated Terraform mock checks and the image security
   gate must succeed. These jobs receive no AWS credentials or OIDC write scope.
3. Only after checks pass, an explicitly enabled publishing job requests environment
   `ecr-release` approval. Only this job has id-token:write, plus contents:read.
   Concurrency is serialized and an in-flight release is not automatically cancelled.
4. Publishing job checks out the exact dispatched SHA, builds linux/amd64 with the
   reviewed Alpine Dockerfile and dependency configuration, scans that actual image
   with fresh Trivy data, and runs /health /ready /version /metrics without a database.
   This second build is intentional: there is no image archive transfer artifact;
   the exact image pushed is scanned and runtime-tested on the publishing runner.
5. Only after that gate does the pinned official AWS Action exchange GitHub OIDC for
   a 900-second role session. Existing credentials are unset; no permanent AWS keys
   are configured. Expected account is enforced and account IDs masked.
6. Helper checks the exact existing Sydney repository, strict IMMUTABLE tags and
   scan-on-push. It refuses any existing git-<12-character-commit> tag. It cannot
   create/change the repository, delete images or alter tag mutability.
7. The scanned archive checksum/config are verified and reloaded before tagging.
   Docker login uses stdin and an isolated temporary Docker config; it is logged
   out and removed afterward. Token, registry URI and raw Docker/AWS output are not
   printed or uploaded. Credentials arrive only after app container tests finish.
8. Remote tag digest must match Docker's reported push digest. Manifest bytes are
   hashed; a single-manifest image is handled directly, or exactly one Linux AMD64
   child is resolved from an OCI index. Its config digest must match the scanned
   local archive, binding platform, metadata and rootfs identity. This avoids treating
   Docker-classic config IDs and OCI index IDs as interchangeable.
9. ECR scan-on-push is polled on the child digest. HIGH/CRITICAL failures fail the
   workflow after push and record review-required evidence. An incomplete scan is
   not a successful release. No automatic image deletion or ECS deployment follows.

A completed local build/scan marked `local_validation_only=true` **cannot be
published** by the helper. Source must be clean and match GITHUB_SHA in a real
manual main-branch run. Explicit recipe hashes detect unreviewed Dockerfile or
pyproject changes and require a future review/update. Dependency ranges and apk
repositories still move; Git-derived tags do not establish bit-for-bit reproduction.
The exporter disables attached provenance attestations for classic Docker-store
compatibility. Evidence binds commit, recipe, config, root and child digests; it
is not an independently signed SLSA attestation.

## Prepared IAM configuration - no architecture changes

Review-only JSON templates:

- [Trust template](iam/ecr-release-trust.json.example)
- [Repository permission template](iam/ecr-release-permissions.json.example)
- Local renderer: `scripts/render_release_iam.py`

No Terraform module/root/backend is changed or wired to create this role. Keep
this role separate from ECS task/execution roles and the human Terraform deployer.
Proposed role name: **rdp-github-ecr-release**, max session duration3600 seconds;
workflow requests only900 seconds. Reuse a reviewed existing GitHub OIDC provider,
or obtain separate approval to provision one. Issuer is
https://token.actions.githubusercontent.com and audience sts.amazonaws.com.

Trust requires StringEquals on audience and the **exact confirmed subject for this
repository's ecr-release environment**. No wildcard repository/branch/environment.
AWS does not generally accept arbitrary GitHub custom claims as separate IAM keys;
branch restriction is enforced by the GitHub environment and workflow guards, not
an invented `:ref` trust condition. [GitHub OIDC guidance](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)
explains environment subjects and recommends deployment protection rules.

**Confirm the subject before rendering/provisioning.** GitHub documents immutable
owner/repository IDs for newer repositories or opt-ins. Depending on the actual
repository configuration, the exact subject can have either shape:

```text
repo:priyanka13-gb/RDP-Aws:environment:ecr-release
repo:priyanka13-gb@OWNER_ID/RDP-Aws@REPO_ID:environment:ecr-release
```

Do not guess IDs, widen trust to a wildcard or print an OIDC JWT. Inspect the
repository's OIDC configuration and verify the subject privately in an approved
OIDC diagnostic run if necessary. A legacy example that mismatches current subject
claims must fail closed. Templates deliberately retain a confirmed-subject
placeholder, so they are **not ready to apply blindly**.

Renderer example, after privately substituting confirmed account/subject values:

```powershell
.venv/Scripts/python.exe scripts/render_release_iam.py --account-id ACCOUNT_ID --subject CONFIRMED_SUBJECT
```

It only writes `.tools/release-iam/trust.json` and `permissions.json`; no AWS call.
Those files contain account-specific configuration and must stay ignored/private.
The renderer accepts exact subjects for this repository/environment, including
immutable-ID variants, and rejects wildcards/other repositories/branch subjects.
Do not put actual account IDs into tracked examples or shell transcripts.

Permissions: repository-scoped ECR upload/layer check/manifest read/repository
metadata/image/scan read. Only GetAuthorizationToken uses Resource:* because AWS
requires it; all statements constrain RequestedRegion to ap-southeast-2.
[Required ECR push actions](https://docs.aws.amazon.com/AmazonECR/latest/userguide/image-push-iam.html)
are included. No ECS, ELB, IAM, S3, Terraform state, CreateRepository, DeleteRepository,
BatchDeleteImage, PutImageTagMutability or scan-configuration permissions. Attach
only this dedicated reviewed policy; do not reuse an administrator/deployer role.
Real effective permissions, OIDC trust, SCPs and Free-plan restrictions remain
untested until separate provisioning approval. Do not upgrade the account or
activate advanced features automatically.

## Required GitHub controls - not configured by this task

Before any publish approval:

1. Review and authorize the workflow/helper/policy changes, then separately approve
   committing/publishing them. Hosted CI and a publish=false manual run must pass.
2. Configure environment `ecr-release`: required independent reviewer(s), prevent
   self-review, disallow protection bypass where supported, and permit only main
   deployments (not tags/other branches). Protect main and review workflow edits.
   If the repository plan cannot enforce these controls, **do not enable publishing**.
   IAM environment-subject trust alone cannot distinguish another workflow granted
   access to the same environment; reviewer/branch controls are essential.
3. Separately approve and create/review the IAM provider/role/policy. Confirm exact
   OIDC subject matches the environment. No resource was created here.
4. Store environment secrets `ECR_RELEASE_ROLE_ARN` and `ECR_RELEASE_ACCOUNT_ID`.
   These are identifiers, not access keys; storing them as secrets prevents account
   IDs appearing in Action input logs. Role ARN must have the dedicated role name.
   No AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY secret is needed or permitted.
5. Only after explicit approval set repository variable
   `ECR_RELEASE_PUBLISH_APPROVED=true`. This task did not set that flag, create an
   environment, store secrets, mint a token or change repository settings.

The approved AWS Action pin and official metadata source are recorded in
[release-action-pin.json](release-action-pin.json). Existing Action pins are reused.
Review covered official release identity, immutable SHA and input/runtime metadata;
it does not claim a full independent audit of bundled dependency code.

## Commands for future approved use - NOT EXECUTED

After separate commit/push approval and merging the reviewed workflow into main:

```powershell
# Validation only; no AWS publishing job runs:
gh workflow run release.yml --ref main -f publish=false
gh run list --workflow release.yml
gh run watch RUN_ID --exit-status
# Only after all external controls/role setup and explicit publish approval:
gh workflow run release.yml --ref main -f publish=true
```

RUN_ID is the numeric GitHub run ID. The workflow must exist on the default branch
before workflow_dispatch can be used. Publish chooses the dispatched main SHA,
not a free-form tag, image or repository input. Existing git-9b18a3109aa2 is never
reused. Re-running the same published SHA intentionally fails at the collision
check. If push succeeded but verification failed, verify that immutable artifact
read-only and review evidence; do not overwrite/delete it or blindly retry.

## Evidence and limitations

Only `.tools/release/scan.json` and `release.json` are uploaded for seven days.
They contain normalized findings, commit/tag, repository name without account,
platform/root/config digests, runtime and scan status. No image tar, build metadata,
auth config, environment dump, token, registry URI or raw service output is uploaded.
If a remote scan fails or times out after push, the image may already exist;
release status must remain unverified/review-required and it must not be deployed.
The ECR scan can differ from Trivy due to coverage/database timing. No findings
are suppressed; HIGH/CRITICAL blocks, all other local findings remain visible.

Local tests cover default-disabled publishing, manual-main context, failed gates,
local-artifact rejection, immutable-tag collision, classic/OCI archive handling,
remote config binding, ambiguous indexes and post-push failed-scan evidence.
Local image build, fresh Trivy scan and runtime endpoints were exercised without
AWS access. OIDC exchange, protected-environment enforcement, real ECR push and
remote digest/scan verification are **not live-tested** under this task's limits.
IAM policies received structural/least-privilege tests, not live AWS provisioning.
Terraform architecture and application/Docker source are unchanged.

Keep publishing **NO-GO** until explicit approval, correct subject/provider/role,
enforced environment protections and successful hosted gates are demonstrated.
There is no automatic ECS/ALB deployment in this design.
