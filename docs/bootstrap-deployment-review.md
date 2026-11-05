# S3 bootstrap deployment review — 5 November 2026

Prepared only: no apply/destroy, bucket creation, state migration or account changes.

## Proposed location

- Bucket: `rdp-tfstate-sydney-be4bb3dfae`
- Region: `ap-southeast-2`; CLI/profile selection: `rdp-dev`
- Dev state: `aws-resilient-delivery-platform/dev/terraform.tfstate`
- Dev lock: `aws-resilient-delivery-platform/dev/terraform.tfstate.tflock`
- Default Terraform workspace only; other workspaces use different paths.

Both variable/backend examples now use this proposed bucket. The dev backend example
and deployment runbook use the requested new key. This changes proposed configuration
only; no backend was connected or existing state moved. Task 8 evidence remains a
historical snapshot of the earlier proposed key.

Read-only AWS checks authenticated successfully. HeadBucket, HeadObject(state) and
HeadObject(lock) returned 404. GetBucketLocation and ListObjectVersions returned
NoSuchBucket. No existing bucket or state was found at this location. These checks
do not reserve a globally unique name; repeat before deployment. A 403 must never
be interpreted as absence. See [sanitized results](../evidence/bootstrap-preflight.json)
and [AWS HeadBucket semantics](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadBucket.html).

## Reviewed protections and exact resource list

Bootstrap has no backend block and initially uses local terraform.tfstate. Dev has
a separate partial S3 backend with encrypt=true and use_lockfile=true. AWS credentials
are supplied by the existing profile through the standard credential chain; there
are no embedded credentials or profile-specific provider changes.

The bootstrap configuration defines exactly these six Terraform resources:

| Address | Effect |
| --- | --- |
| aws_s3_bucket.state | One bucket; force_destroy=false; lifecycle prevent_destroy=true |
| aws_s3_bucket_ownership_controls.state | BucketOwnerEnforced; ACLs disabled |
| aws_s3_bucket_public_access_block.state | All four public-access blocks enabled |
| aws_s3_bucket_versioning.state | Versioning Enabled |
| aws_s3_bucket_server_side_encryption_configuration.state | SSE-S3, AES256 default encryption |
| aws_s3_bucket_policy.https_only | Deny s3:* on bucket and objects when SecureTransport=false |

These are one AWS bucket plus five configuration resources, not six buckets.
Tags include Project=aws-resilient-delivery-platform, Environment=bootstrap,
ManagedBy=Terraform, Name=<bucket>, Purpose=TerraformState. No DynamoDB table, IAM
user, key, NAT, KMS key, ECS or database is created by bootstrap.

Encryption and TLS protect data at rest/in transit; neither replaces authorization.
prevent_destroy protects Terraform operations while that configuration remains; it
does not stop deletion outside Terraform. Versioning is recovery protection, not a
backup against loss of access to the entire account.

## Commands for a later approved deployment

Actual local verification for this review:

- terraform fmt -recursive infra, followed by terraform fmt -check -recursive: passed.
- Bootstrap and dev init -backend=false -input=false: passed after retrying with
  registry network access. Initial sandbox attempts could not reach the registry.
- Bootstrap and dev validate: both passed; existing AWS provider 6.71.0 reused.
- Bootstrap mock-provider plan test: 1 passed, 0 failed. The prior full set of
  22 tests was not rerun. Mock test cleanup did not destroy AWS resources.
- git diff --check: passed. git check-ignore confirmed local state/backups, plans,
  tfvars, backend.hcl and .terraform metadata exclusions; no matching state/backend/
  tfvars/cache paths were tracked. No actual local state exists in either root.
- Review local links and account-ID exclusion checks: passed.

The following commands are instructions, **not executed by this review**. Start in
the repository root. Keep terminal output and saved plans private. Do not proceed
if local bootstrap state or a prior backend exists without first reviewing ownership.

Select the existing profile and remove competing static credentials from this shell
only (this does not edit the AWS credential store):

```powershell
$env:AWS_PROFILE = 'rdp-dev'
$env:AWS_REGION = 'ap-southeast-2'
$env:AWS_DEFAULT_REGION = 'ap-southeast-2'
'AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN','AWS_SECURITY_TOKEN' | ForEach-Object {
    Remove-Item "Env:$_" -ErrorAction SilentlyContinue
}
$bucket = 'rdp-tfstate-sydney-be4bb3dfae'
terraform -chdir=infra/bootstrap init -input=false
terraform -chdir=infra/bootstrap validate
terraform -chdir=infra/bootstrap plan -input=false -var="aws_region=ap-southeast-2" -var="state_bucket_name=$bucket" -out=bootstrap.tfplan
```

Expected: initialization succeeds with local backend; validation reports valid;
plan reports **6 to add, 0 to change, 0 to destroy**, with the exact six addresses
above. This is an expectation based on configuration, not a live plan result.
Stop on any unexpected resource, existing state, region mismatch, permission error
or different count. Never use -migrate-state or -force-copy.

Review the saved plan and obtain explicit approval for this bucket and plan. Only
then execute the first apply:

```powershell
terraform -chdir=infra/bootstrap apply bootstrap.tfplan
```

Expected: **Resources: 6 added, 0 changed, 0 destroyed**, plus bucket name and S3
bucket ARN outputs. Saved-plan apply does not ask for another confirmation; approval
must precede the command. Back up infra/bootstrap/terraform.tfstate and its backup
securely outside Git immediately. Never lose bootstrap state or upload it as dev state.

## Read-only checks after creation

Use these only after the approved creation, with the same $bucket value:

```powershell
$awsArgs = @('--profile','rdp-dev','--region','ap-southeast-2','--no-cli-pager')
aws s3api head-bucket --bucket $bucket @awsArgs
aws s3api get-bucket-location --bucket $bucket @awsArgs
aws s3api get-bucket-versioning --bucket $bucket @awsArgs
aws s3api get-bucket-encryption --bucket $bucket @awsArgs
aws s3api get-public-access-block --bucket $bucket @awsArgs
aws s3api get-bucket-ownership-controls --bucket $bucket @awsArgs
aws s3api get-bucket-tagging --bucket $bucket @awsArgs
aws s3api get-bucket-policy --bucket $bucket @awsArgs
$stateKey = 'aws-resilient-delivery-platform/dev/terraform.tfstate'
aws s3api head-object --bucket $bucket --key $stateKey @awsArgs
aws s3api head-object --bucket $bucket --key "$stateKey.tflock" @awsArgs
aws s3api list-object-versions --bucket $bucket --prefix $stateKey --query '{Versions:Versions[].Key,DeleteMarkers:DeleteMarkers[].Key}' @awsArgs
```

Expect successful bucket access, Sydney location, Enabled versioning, AES256,
four true block flags, BucketOwnerEnforced, the documented tags and TLS deny policy.
For a new empty bucket, both object reads should report not found and version lists
should be empty/null. Investigate 403, existing versions or locks; do not delete them.
Verify ownership privately against the authenticated identity; do not publish IDs.

After those checks and separate backend-initialization authorization, create ignored
infra/envs/dev/backend.hcl from its example without overwriting an existing file.
Recheck its bucket/key/region/locking and initialize the *new empty* dev backend:

```powershell
terraform -chdir=infra/envs/dev init -backend-config=backend.hcl -input=false
```

Stop if Terraform proposes copying state. Bootstrap state remains local. Native S3
locking needs ListBucket for the prefix, GetObject/PutObject on the state object and
GetObject/PutObject/DeleteObject on .tflock. It does not need DeleteObject on state.
No DynamoDB table is required. Lock functionality cannot be exercised read-only
before bucket creation. [HashiCorp backend and permissions](https://developer.hashicorp.com/terraform/language/backend/s3).

## Cost and recovery

S3 usage includes stored current and noncurrent state versions, requests and applicable
transfer. For small infrequently updated state this is generally small, but it is
not guaranteed free. There is no fixed compute/NAT charge in this bootstrap and no
customer-managed KMS key or DynamoDB cost. SSE-S3 avoids separate KMS requests/key
charges. Consult [current S3 pricing](https://aws.amazon.com/s3/pricing/) for Sydney;
no exact monthly estimate is possible without state size and update frequency.

No expiration lifecycle is configured, so old versions accumulate. Keep a secure
independent backup. To recover later: stop concurrent Terraform activity, inspect
version history, retrieve the selected version privately, compare lineage/serial
and actual resources, then obtain approval for restoration. Do not overwrite state
or remove locks during diagnosis. Never restore bootstrap state into the dev key.

## Remaining gates and permission uncertainty

- Review and approve a real bootstrap plan before the first apply; none was run here.
- Reconfirm the random bucket name has not been taken and credentials are current.
- Task 8's 32 context-aware simulated actions passed, including sampled S3 creation
  settings. This review confirms read access only, not actual write permissions.
  Bucket tagging/readback and exact resource/session policies still matter; simulation
  is not a guarantee. No Free-plan restriction or AccessDenied was observed in these
  S3 preflight calls. No advanced features were activated.
- Do not initialize dev remotely until the bucket and state/lock safety checks pass.
- Decide where to keep the secure bootstrap-state backup before creating resources.

The application, Docker and PostgreSQL files are unchanged.
