# Isolated ECR root

This root exclusively owns the development ECR repository and lifecycle policy,
reusing ../../modules/ecr. It creates no networking, ECS, ALB, RDS or IAM resources.
The module preserves immutable tags, AES256 encryption, scan-on-push, 20-image
retention and force_delete=false. Retention can expire rollback images and is not
a dollar or storage-size ceiling.

## State ownership

| Root | State | Ownership |
| --- | --- | --- |
| infra/bootstrap | Local terraform.tfstate | S3 bucket and protections |
| infra/envs/ecr | aws-resilient-delivery-platform/ecr/terraform.tfstate | Repository and lifecycle policy |
| infra/envs/dev | aws-resilient-delivery-platform/dev/terraform.tfstate | Network, IAM, logs, ALB and ECS |

Both remote roots use rdp-tfstate-sydney-be4bb3dfae in ap-southeast-2, encryption
and native .tflock locking. Use AWS_PROFILE=rdp-dev through environment variables.
Backend/provider configuration contains no credentials. Changing environment/region
variables does not change backend keys: review both before any such change.

Dev reads data.aws_ecr_repository.app in its provider account/region using the same
environment-derived name. It needs ECR DescribeRepositories access, not read access
to ECR Terraform state. The repository must exist before a real dev plan succeeds.
Dev destruction will not delete ECR. Keep required images until all consumers and
rollback requirements are retired before considering separately approved ECR deletion.

Task 14 confirmed dev has zero managed resources and the repository is absent.
Therefore no state move/import is required. Another checkout with existing dev-owned
ECR requires a separately reviewed ownership transition; never blindly remove state.

## Future deployment commands

From the repository root, select the existing profile and ensure competing static
credential variables are absent. Keep account-specific plans/output private.

```powershell
$env:AWS_PROFILE = 'rdp-dev'
$env:AWS_REGION = 'ap-southeast-2'
$env:AWS_DEFAULT_REGION = 'ap-southeast-2'
terraform -chdir=infra/envs/ecr init -input=false
terraform -chdir=infra/envs/ecr validate
terraform -chdir=infra/envs/ecr plan -input=false -out=ecr.tfplan
```

Review exactly two creates, no changes/deletes. No -target is needed. Planning
uses and releases a temporary S3 lock; it does not apply resources. Do not disable
locking to bypass concurrency or permissions errors.

Only after explicit approval of the saved plan:

```powershell
terraform -chdir=infra/envs/ecr apply ecr.tfplan
```

Saved-plan apply does not prompt for another confirmation. Replan/review if another
operator changes state or creates the repository. Never import/overwrite automatically.
After apply, verify settings, then upload a separately approved tested linux/amd64
image with an immutable Git-derived tag. Use its digest URI for container_image in
dev, and review a full dev plan separately. No apply or image push ran in Task 14.

This root supersedes the Task 12 targeted-dev ECR procedure. Dev no longer owns
module.ecr. State, backend caches and *.tfplan are ignored; the provider lockfile is
intended for version control. Preserve bootstrap local state backups independently.
