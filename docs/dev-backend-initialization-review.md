# Dev backend initialization review — Task 11

Result: safe to perform fresh initialization based on the checks below. Initialization
has deliberately not been run. Recheck state/lock paths immediately before proceeding
if another operator could have used them since this review.

## Actual inspection

- Bootstrap local terraform.tfstate contains six managed resources/instances: bucket,
  ownership controls, public-access block, versioning, encryption and bucket policy.
  Bootstrap has no remote backend block. Its state was read only and checksum-checked.
- Existing-profile authentication succeeded. S3 requests used rdp-dev, Sydney, and
  an expected-owner check against the authenticated account without displaying its ID.
- Bucket location is ap-southeast-2; SSE-S3 AES256 encryption and versioning are enabled.
  All four public-access blocking settings are true. Policy denies all S3 actions
  for insecure transport on both bucket and objects.
- No local dev state, state backup, workspace state, backend metadata or workspace
  selection file was found under infra/envs/dev. No backend.hcl previously existed.
- Exact target state and .tflock HeadObject requests returned 404. ListObjectVersions
  succeeded and found zero versions/delete markers for either exact key. No S3
  object contents were read or written.

Evidence: [local inspection](../evidence/dev-backend-local-inspection.json) and
[AWS inspection](../evidence/dev-backend-aws-inspection.json). The local evidence
records the pre-preparation snapshot, before backend.hcl was created.

## Prepared configuration

Created ignored infra/envs/dev/backend.hcl:

```hcl
bucket       = "rdp-tfstate-sydney-be4bb3dfae"
key          = "aws-resilient-delivery-platform/dev/terraform.tfstate"
region       = "ap-southeast-2"
profile      = "rdp-dev"
encrypt      = true
use_lockfile = true
```

The existing partial S3 backend in versions.tf is preserved. The profile name is
not a credential. The provider uses the standard credential chain; set AWS_PROFILE
in the initialization/deployment shell as well so backend and provider agree.

## Future initialization procedure

Only after authorization to initialize, run from the repository root. Ensure the
existing profile login is current and no concurrent Terraform process is using dev.
Check state/lock metadata again using the exact keys and the same identity; stop on
403, new objects/versions, a lock, or unexpected local state. Never remove a lock or
overwrite state to make initialization proceed.

```powershell
$env:AWS_PROFILE = 'rdp-dev'
$env:AWS_REGION = 'ap-southeast-2'
$env:AWS_DEFAULT_REGION = 'ap-southeast-2'
'AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN','AWS_SECURITY_TOKEN' | ForEach-Object {
    Remove-Item "Env:$_" -ErrorAction SilentlyContinue
}
terraform -chdir=infra/envs/dev init -backend-config=backend.hcl -input=false
terraform -chdir=infra/envs/dev validate
```

Removing these environment variables affects this shell only, not saved credentials.
Expected: successful S3 backend initialization and validation, with no resources
created. Initialization records local backend metadata; it is not a deployment.
No state migration or -reconfigure flag is currently needed because there is no
previous dev state/backend to preserve. Do not use -migrate-state or -force-copy.
If Terraform requests migration/reconfiguration, stop and reassess the newly observed
state rather than applying a flag automatically. Never run init in bootstrap with
the dev backend file. Its six-resource local state must stay separate.

After initialization, privately inspect only the backend metadata fields to confirm
bucket/key/region/profile, default workspace and locking. Repeat read-only S3 state
and lock checks; an empty backend need not contain a state object yet. Do not create
a dummy state/lock object to test it. Do not run apply as a verification step.

## Permissions and verification limits

Read checks succeeded. They do not prove PutObject/DeleteObject permissions or
lock acquisition. Future operations need scoped ListBucket, GetObject/PutObject
on state, and GetObject/PutObject/DeleteObject on the .tflock object. Keep these
permissions on the Terraform operator, not the app role. There is no need to move
bootstrap state or create a DynamoDB table.

Formatting and dev validation passed using already-installed providers. No init was
needed for local validation. Git ignores backend.hcl, local bootstrap state and
.terraform metadata. No apply/destroy, remote write, migration, resource creation,
credential change or Git push was performed. Application files were untouched.
