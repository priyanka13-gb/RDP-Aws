# State bootstrap and recovery

See the [first-apply review](../../docs/bootstrap-deployment-review.md) for the historical proposed
bucket and first-apply commands. The bootstrap bucket has since been deployed;
retain its local state and use read-only checks before any future changes. The dev state key is
`aws-resilient-delivery-platform/dev/terraform.tfstate`.

This is a separate Terraform root with **local state**. It defines a private S3
bucket with ownership enforcement, all public-access blocks, versioning, SSE-S3
encryption, and an HTTPS-only bucket policy. `prevent_destroy` and `force_destroy=false`
protect state data. There is no DynamoDB table, IAM user, access key, or remote backend
in this root. Local state and backup files are already ignored by Git.

The default region and examples are **ap-southeast-2 (Sydney)**. The dev backend
region is configured independently in `backend.hcl`; it must match the actual
state bucket location. No existing bucket or state is moved by editing defaults.

## Validate without AWS resources

```powershell
terraform -chdir=infra/bootstrap init -backend=false
terraform -chdir=infra/bootstrap validate
terraform -chdir=infra/bootstrap test
```

All tests explicitly use a mock provider and `command = plan`. Terraform >=1.10 is
required for S3-native locking; this project is tested with 1.17.1.

## Future bootstrap process (requires separate deployment authorization)

1. Select the AWS account and region using short-lived role/SSO credentials. Nothing
   in this repository configures credentials.
2. Copy `terraform.tfvars.example` to ignored `terraform.tfvars` and choose a globally
   unique bucket name. Review a bootstrap plan, then obtain deployment approval.
3. Only after authorization, deploy this bootstrap root. Its initial state stays
   local: securely back up that state outside Git. The bucket does not manage its
   own backend. Do not lose the local state after bootstrap.
4. Copy `../envs/dev/backend.hcl.example` to ignored `../envs/dev/backend.hcl`. Fill
   in the actual bucket name, key and region. Do not add credentials.
5. For a new, empty dev state, initialize the dev backend with
   `terraform -chdir=infra/envs/dev init -backend-config=backend.hcl` only after the
   bucket exists and remote initialization is authorized. If Terraform reports
   existing state or requests migration, stop and review it separately. No state
   migration is part of this implementation.

The dev backend sets `use_lockfile=true` and encryption. The deployment identity
will need scoped `s3:ListBucket` access, `s3:GetObject`/`s3:PutObject` for the selected
state key, and `s3:GetObject`/`s3:PutObject`/`s3:DeleteObject` for that key's `.tflock`
object. Do not grant broad bucket access to the ECS application role. Workspace
prefixes need additional scoped paths if non-default Terraform workspaces are used.
This milestone uses only the default workspace and the explicit dev state key.

SSE-S3 avoids a customer-managed KMS key's separate cost. It does not make state
safe to publish: state can contain sensitive infrastructure information. This root
does not impose lifecycle expiration on state versions; review growing storage costs
and recovery requirements before adding any retention policy.

Reference: [HashiCorp S3 backend and lockfile permissions](https://developer.hashicorp.com/terraform/language/backend/s3).
