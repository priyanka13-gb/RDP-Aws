# Task 14 result

Implemented isolated ECR ownership. No apply/destroy, image push, state migration,
credential change or Git push was performed. No AWS infrastructure was created.

## Actual plan

Normal full-root plan, without targeting: **2 to add, 0 to change, 0 to destroy**.

- module.ecr.aws_ecr_repository.this
- module.ecr.aws_ecr_lifecycle_policy.this

Repository: aws-resilient-delivery-platform-dev. Plan confirms IMMUTABLE tags,
AES256 encryption, scan-on-push and consistent Project/Environment/ManagedBy/Component
tags. Existing module retains 20 images and rejects force deletion of populated ECR.
No VPC, subnet, NAT, ECS, ALB, RDS or IAM changes exist in this plan.

Saved plan: infra/envs/ecr/ecr.tfplan (ignored; contains private account-specific data).
[Sanitized plan review](task14-ecr-plan.json) and [preflight](task14-preflight.json).
Before initialization, both new key and lock were absent and had no historical
versions. Dev owned zero managed resources and ECR was absent. After planning,
ECR state and current lock objects both returned 404. Planning acquired/released
a temporary native lock, which can leave a historical lock version in a versioned
bucket; it did not write managed state or overwrite any existing state.

## Verification

- Formatting and recursive fmt check: passed.
- New ECR remote-backend initialization: passed; existing provider 6.71.0 selected.
- Dev module initialization with -backend=false: passed; no dev backend migration.
- ECR, dev, bootstrap and network validation: all passed.
- Mock-plan tests: ECR 1, dev 16, bootstrap 1, network 5; **23 passed, 0 failed**.
- git diff --check and ignored plan/backend-cache checks: passed.

[Command results](task14-validation.json). Mock test cleanup is not an AWS destroy.

## Files changed for this task

- infra/envs/ecr/{versions,main,variables,outputs}.tf: isolated backend/provider and
  module reuse, defaults and outputs.
- infra/envs/ecr/.terraform.lock.hcl: provider lock seeded from dev and verified by init.
- infra/envs/ecr/tests/root.tftest.hcl and README.md: root test and deployment/state guide.
- infra/modules/ecr/outputs.tf: added repository_name output; resource settings unchanged.
- infra/envs/dev/main.tf: replaced ECR module ownership with aws_ecr_repository lookup;
  IAM and ECS consume that lookup. Other module configuration preserved.
- infra/envs/dev/outputs.tf: repository URL now comes from the data source.
- infra/envs/dev/tests/wiring.tftest.hcl: mocked lookup instead of managed repository.
- README.md and earlier deployment guides: document new ownership and supersede targeting.
- Task 14 evidence files: sanitized checks, test results and plan summary.

## Next commands and remaining gates

No blocker remains for reviewing this ECR creation plan. Actual creation still requires
approval, and a plan does not guarantee apply permissions. Use the existing profile
with no competing static credential environment variables. After explicit approval:

```powershell
$env:AWS_PROFILE = 'rdp-dev'
$env:AWS_REGION = 'ap-southeast-2'
$env:AWS_DEFAULT_REGION = 'ap-southeast-2'
terraform -chdir=infra/envs/ecr apply ecr.tfplan
```

If configuration, repository existence or state changes before approval, regenerate
and review with `terraform -chdir=infra/envs/ecr plan -input=false -out=ecr.tfplan`.
Do not use -target. Saved-plan apply requires no further CLI confirmation.

Dev real planning now intentionally requires this repository to exist. After ECR
creation, separately verify/build a linux/amd64 image, approve its push, and supply
its immutable tag/digest for a normal dev plan. Docker verification remains outside
this task. ECR storage/transfer and S3 state requests/versions can consume credits;
20-image retention is not a spending cap. See the
[state separation and deployment guide](../infra/envs/ecr/README.md).
