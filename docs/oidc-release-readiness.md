# Task 33 — OIDC release provisioning review

> Archived design: Task34 defers OIDC and retains the AWS Free plan. Do not execute
> the provisioning, settings or dispatch steps below for portfolio finalization.
> See [current portfolio status](portfolio-status.md) and the
> [temporary-credential manual release procedure](manual-ecr-temporary-credentials.md).

14 November 2026 IST. **NO-GO for provisioning/publishing until the audit gaps
and separate approval are resolved.** All AWS/GitHub calls in this review were
read-only. No IAM object, GitHub setting, workflow dispatch, commit or push was
performed. The working tree contains review files only.

## Actual audit findings

| Check | Result |
| --- | --- |
| Repository | Public, `priyanka13-gb/RDP-Aws`, main at `693efb2fd5f83c1ce60a6a029bd6f65223765d70` |
| Hosted CI | [43487727943](https://github.com/priyanka13-gb/RDP-Aws/actions/runs/43487727943) SUCCESS, verified in Task 32 |
| GitHub OIDC settings | use_default=true, use_immutable_subject=true; exact prefix returned by repository API |
| Release environment | Environment list empty; `ecr-release` does not exist |
| Main branch protection | protected=false |
| Release enablement variable | Absent, therefore publishing is disabled by workflow guards |
| Identifier / permanent AWS key secrets | No expected identifier secrets or standard AWS access-key secret names found at repository level; no release environment exists |
| Account plan name | Authenticated user API omitted plan data; exact subscription is unverified |
| AWS authentication | rdp-dev succeeds; region ap-southeast-2 |
| OIDC provider inventory | ListOpenIDConnectProviders and targeted GetOpenIDConnectProvider both AccessDenied; existence/configuration UNKNOWN |
| Release role | GetRole returned NoSuchEntity for rdp-github-ecr-release |
| ECR | Existing repository IMMUTABLE, scan-on-push enabled, AES256 encryption |
| Terraform | github_oidc module is an empty placeholder; existing IAM module defines ECS roles only; no OIDC root/provider/role is wired into deployment |

GitHub's [current public-repository environment rules](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)
support required reviewers and deployment-branch restrictions on current plans.
This repository is public, so private-repository plan limits do not block those
features. Exact account subscription/legacy entitlements were not returned; verify
the controls in Settings before enabling anything. Do not change visibility or
upgrade a plan as part of this procedure.

## Exact trust and least privilege

The configured future environment subject is:

```text
repo:priyanka13-gb@98728444/RDP-Aws@1444281868:environment:ecr-release
```

The IDs and immutable prefix came from authenticated repository/OIDC metadata,
not a guessed namespace. The environment suffix follows GitHub's
[documented subject format](https://docs.github.com/en/actions/reference/security/oidc).
No runtime JWT has been requested or observed in this task. Refresh metadata after
a rename/transfer/OIDC-template change and verify the first approved STS exchange.

[Trust template](iam/ecr-release-trust.json.example) now uses that exact subject
and `StringEquals` audience `sts.amazonaws.com`, with only the account-specific
GitHub provider principal. AWS account remains a placeholder in tracked files.
Concrete rendered trust/permissions are privately prepared under ignored
`.tools/release-iam/`. No wildcard repo, alternate subject or broad trust is allowed.

[Permission template](iam/ecr-release-permissions.json.example) is unchanged:

- `ecr:GetAuthorizationToken` on `*`, restricted to Sydney. This authentication
  API cannot be scoped to one repository; it does not itself grant image writes.
- DescribeRepositories, DescribeImages, BatchGetImage, BatchCheckLayerAvailability,
  InitiateLayerUpload, UploadLayerPart, CompleteLayerUpload, PutImage and
  DescribeImageScanFindings on the single existing repository ARN in Sydney.
- No repository creation/deletion, image deletion, ECS, ELB, S3/state, IAM admin,
  PassRole or Terraform permissions. Registry authentication does not bypass
  resource-scoped ECR permissions. See [ECR authentication requirements](https://docs.aws.amazon.com/AmazonECR/latest/userguide/repository-policies.html).

The role can publish any new tag in this one repository; Git-derived tag naming
and manual-event/source guards are workflow controls, while ECR enforces immutable
existing tags. Environment-subject trust can be used by another job in this repo
that references the same environment; it does not cryptographically pin one
workflow file. Protected main and independent environment approval are essential.

The manual release remains workflow_dispatch only, publish=false by default,
serialized, main-only, gated by reusable CI and a fresh scan/runtime check of the
actual publishing image before credentials. Only its publish job receives
id-token:write. It requests 900-second credentials, masks account IDs and refuses
existing tags. It verifies root/AMD64/config digests and completed ECR scan. No
permanent access-key inputs, ECS/ALB deployment or Terraform operation is present.

## Resources and GitHub controls requiring separate approval

AWS objects required:

1. **Zero or one** GitHub IAM OIDC provider for
   `https://token.actions.githubusercontent.com`, with sts.amazonaws.com audience.
   Inventory is denied: an authorized administrator must check and reuse an
   existing provider before considering creation. Do not mutate a shared provider
   without reviewing its other consumers.
2. One IAM role `rdp-github-ecr-release`, exact trust above, maximum session
   duration 3600 seconds (IAM minimum maximum); workflows request only 900 seconds.
3. One inline policy `rdp-ecr-publish` on that role using the existing template.
   No standalone managed policy, access key, instance profile, ECR repository,
   S3 bucket, network, ECS, ALB or paid infrastructure is required.

The human provisioning principal needs narrowly approved ListOpenIDConnectProviders
(a read-only list on `*`), GetOpenIDConnectProvider, CreateOpenIDConnectProvider,
TagOpenIDConnectProvider, GetRole, CreateRole, TagRole, PutRolePolicy and
GetRolePolicy permissions as applicable, scoped to these objects where supported.
IAM providers/roles are global; Sydney restrictions apply to the ECR permissions.
The publisher
does not receive those permissions. AccessDenied on provider reads does not prove
provider absence or permission to create it. SCPs/boundaries/Free-plan restrictions
and effective provisioning permissions remain unverified; do not fix this by
granting broad AdministratorAccess to the release role.

GitHub owner actions, not executed:

1. Create `ecr-release`. Require an independent trusted reviewer who has repository
   access; prevent self-review and disable administrator bypass where supported.
   If only the initiator can approve, add a legitimate reviewer before enabling.
2. Permit only the **branch** main; do not permit matching tags or arbitrary
   branches. Use a selected branch policy rather than relying on currently absent
   branch protection. Protect main with PR review and successful CI checks; review
   workflow/IAM-policy edits and restrict bypasses.
3. After approved IAM provisioning, store ECR_RELEASE_ROLE_ARN and
   ECR_RELEASE_ACCOUNT_ID as environment secrets. These are identifiers, not
   access keys. Never add AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY.
4. Keep ECR_RELEASE_PUBLISH_APPROVED absent/false through authentication validation.
   Set it true only under explicit publishing approval after all controls pass.

## Future provisioning commands — NOT EXECUTED

Run only after separate approval, a successful authorized provider audit and
GitHub protections. Existing rdp-dev must be authorized; otherwise use an approved
administrator session without changing credentials in this task. All private
files stay ignored; do not echo account IDs or command JSON to shared logs.

```powershell
$releaseAccount = aws sts get-caller-identity --query Account --output text --profile rdp-dev --region ap-southeast-2
if ($LASTEXITCODE -ne 0) { throw 'Authentication failed' }
$oidcArn = "arn:aws:iam::${releaseAccount}:oidc-provider/token.actions.githubusercontent.com"
aws iam get-open-id-connect-provider --open-id-connect-provider-arn $oidcArn --profile rdp-dev --region ap-southeast-2 > .tools/release-iam/provider-private.json 2> .tools/release-iam/provider-error-private.txt
$providerReadExit = $LASTEXITCODE
if ($providerReadExit -eq 0) {
    $existingProvider = Get-Content .tools/release-iam/provider-private.json -Raw | ConvertFrom-Json
    if ($existingProvider.Url.TrimEnd('/') -notin @('token.actions.githubusercontent.com', 'https://token.actions.githubusercontent.com') -or $existingProvider.ClientIDList -notcontains 'sts.amazonaws.com') {
        throw 'Existing provider mismatch; stop for shared-provider review'
    }
} elseif ((Get-Content .tools/release-iam/provider-error-private.txt -Raw) -match '\(NoSuchEntity\)') {
    # Only after absence is confirmed AND creation is separately approved:
    aws iam create-open-id-connect-provider --url https://token.actions.githubusercontent.com --client-id-list sts.amazonaws.com --tags Key=Project,Value=aws-resilient-delivery-platform Key=Environment,Value=dev Key=ManagedBy,Value=ManualReviewed --profile rdp-dev --region ap-southeast-2 > .tools/release-iam/provider-created-private.json
    if ($LASTEXITCODE -ne 0) { throw 'Provider creation failed; inspect privately, do not blindly retry' }
} else {
    throw 'Provider audit failed (including AccessDenied); creation is prohibited'
}

# Refresh metadata and render exact trust before creation; account stays private:
.venv/Scripts/python.exe scripts/render_release_iam.py --account-id $releaseAccount --subject 'repo:priyanka13-gb@98728444/RDP-Aws@1444281868:environment:ecr-release'
if ($LASTEXITCODE -ne 0) { throw 'Policy rendering failed' }
aws iam create-role --role-name rdp-github-ecr-release --assume-role-policy-document file://.tools/release-iam/trust.json --max-session-duration 3600 --tags Key=Project,Value=aws-resilient-delivery-platform Key=Environment,Value=dev Key=ManagedBy,Value=ManualReviewed --profile rdp-dev --region ap-southeast-2 --query Role.RoleName --output text
if ($LASTEXITCODE -ne 0) { throw 'Role creation failed; do not alter an existing role blindly' }
aws iam put-role-policy --role-name rdp-github-ecr-release --policy-name rdp-ecr-publish --policy-document file://.tools/release-iam/permissions.json --profile rdp-dev --region ap-southeast-2
if ($LASTEXITCODE -ne 0) { throw 'Role exists but policy attachment failed; publishing remains disabled' }
```

These are conditional steps, not a copy-and-run script: skip provider creation
when reusing an existing reviewed provider. The current provider audit blocker
must be resolved first. Thumbprints are deliberately not hardcoded; current
[AWS CLI behavior](https://docs.aws.amazon.com/cli/latest/reference/iam/create-open-id-connect-provider.html)
retrieves the CA thumbprint if omitted. Re-read URL/audiences/trust/inline policy
privately after creation and compare to reviewed files before GitHub enablement.
Do not log raw GetRole responses or copy account-specific files into Git.

IAM itself has [no additional service charge](https://docs.aws.amazon.com/IAM/latest/UserGuide/iam-ug.pdf).
ECR storage/scanning, data transfer and GitHub Actions usage can incur charges;
existing lifecycle retention still applies. No account-plan change, paid scanner,
NAT, database, ECS or ALB is introduced by this plan.

## Authentication and release verification

The existing release workflow with publish=false runs tests only; it **does not
test OIDC**. Do not use publish=true merely to test authentication, because that
path will push an image. A separate review-only
[authentication workflow template](iam/oidc-auth-check.yml.example) is prepared.
It requests OIDC in the protected environment, verifies STS identity without
printing it, and describes the existing repository. Its session policy intersects
the role with read-only DescribeRepositories, excluding ECR image writes.

After separate approval to install/publish this template as
`.github/workflows/oidc-auth-check.yml`, and after IAM/environment setup:

```text
gh workflow run oidc-auth-check.yml --repo priyanka13-gb/RDP-Aws --ref main
gh run watch AUTH_RUN_ID --repo priyanka13-gb/RDP-Aws --exit-status
gh workflow run release.yml --repo priyanka13-gb/RDP-Aws --ref main -f publish=false
```

GitHub CLI is not currently installed; use the GitHub Actions UI or an approved
CLI setup later. No software installation was performed here. Authentication
success requires the intended environment approval, a successful STS exchange
against the exact trust and read-only ECR check. JWTs/temporary credentials must
not be logged or uploaded. Keep the run ID and sanitized boolean result; review
CloudTrail privately if permissions allow. No real OIDC exchange was tested now.

Only after those checks and explicit release approval, enable the variable and
manually dispatch release.yml on reviewed main with publish=true. Verify all
required gates and environment approval, a new git-<12-character-SHA> tag,
linux/amd64/non-root runtime, matching remote root and child/config identity,
completed ECR scan and sanitized artifacts. Fail/timeout after push means the
artifact may exist but is not approved: inspect read-only; never overwrite it or
blindly rerun the tag. Never dispatch ECS/ALB or Terraform deployment.

## Revocation — future approved incident response only

First disable publishing and cancel active release jobs in GitHub. Removing a
variable blocks future workflow pushes but does not revoke issued credentials.
An authorized administrator can immediately deny all role activity by attaching
this dedicated-role-only emergency policy (an explicit deny, not a privilege grant):

```json
{"Version":"2012-10-17","Statement":[{"Effect":"Deny","Action":"*","Resource":"*"}]}
```

Save it privately as `.tools/release-iam/deny-all.json`, then, only with approval:

```powershell
aws iam put-role-policy --role-name rdp-github-ecr-release --policy-name emergency-deny-all --policy-document file://.tools/release-iam/deny-all.json --profile rdp-dev --region ap-southeast-2
```

Keep that deny in place while investigating. Remove the publish inline policy,
remove access via trust, and use IAM's
[revoke sessions procedure](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_revoke-sessions.html)
if timestamp-based revocation is preferred. Workflow sessions request 15 minutes,
but the role permits up to one hour and ECR authorization tokens have their own
lifetime: do not rely solely on waiting or changing trust to stop existing access.
Verify revocation with an approved negative test after propagation; no such test
was executed now. Delete the dedicated role only after its policies and consumers
are reviewed. Never delete a shared GitHub OIDC provider or other release images.
Review CloudTrail/ECR for unexpected tags without deleting immutable evidence.

## Local validation and decision

Actionlint passed for CI, release and the inactive auth-check template; Ruff passed.
93 Linux unit tests passed (including 20 release/IAM tests); four opt-in integration
tests were deselected. Concrete policies were parsed and checked for exact subject,
audience, one ECR repository and template parity. This is structural validation,
not IAM Access Analyzer validation, policy simulation or live STS evidence.
No permanent credentials were used by the proposed workflows.

**GO for review; NO-GO for AWS provisioning or publishing.** Resolve OIDC read
permissions/provider inventory, establish independently reviewed main/environment
protections, obtain separate approval, then validate authentication before enabling
release. No changes have been committed or pushed by Task 33.
