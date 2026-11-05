# Sydney region configuration verification — 2026-11-05

Deployment defaults now target **ap-southeast-2 (Sydney)**. No AWS resources,
credentials, image pushes, backend connections, state migration, apply/destroy or
Git pushes were performed. Existing uncommitted infrastructure work was preserved.

## Changes

- Bootstrap and dev default region: ap-southeast-2.
- Bootstrap/dev variable examples, backend example, ECR image example and current
  deployment documentation updated to Sydney.
- Dev now discovers available standard AZs in its provider region, sorts them and
  selects two when `availability_zones=[]`. Local Zones are excluded. An explicit
  ordered pair remains supported and is checked against the discovered availability.
- Selected AZs are exposed through the `availability_zones` output. Preserve/pin
  that order before later changes to an already deployed environment.
- Mock regional ARNs, ECR URIs and AZ fixtures now use Sydney. Added checks for
  dynamic sorted selection and explicit AZ order preservation.

## Actual results

Terraform 1.17.1; AWS provider 6.71.0, unchanged lockfiles.

| Check | Result |
| --- | --- |
| `terraform fmt -recursive` | Completed |
| `terraform fmt -check -recursive` | Passed, exit 0 |
| Bootstrap init -backend=false / validate | Passed |
| Dev init -backend=false / validate | Passed, including referenced modules |
| Network init -backend=false / validate | Passed |
| Dev mock-plan tests | **16 passed, 0 failed** |
| Network mock-plan tests | **5 passed, 0 failed** |
| Bootstrap mock-plan tests | **1 passed, 0 failed** |
| `git diff --check` | Passed; existing CRLF policy notices only |

All initialization commands used `-input=false -lockfile=readonly` and reused the
installed provider using `-plugin-dir=.terraform/providers`. No remote backend was
initialized. The initial two new AZ test assertions failed because a list was compared
with a tuple; explicitly converting expectations to lists fixed the tests. The final
complete dev suite passed. Total: **22 passing mock-plan tests**.

## Region assumption review and preservation

- No remaining `ap-south-1` or `Mumbai` references in active infra, scripts, current
  docs, README or workflow files. Older evidence reports remain historical records.
- No region-specific EC2 AMI IDs: the app uses Linux/X86_64 Fargate.
- IAM ECS trust and KMS service conditions derive region/partition from the provider.
- CloudWatch task log configuration receives the selected region from dev.
- Optional SSM/KMS ARNs and the actual ECR image remain operator inputs; use real
  Sydney resources when configuring them. The backend region is independent and
  must match the actual state bucket's location.
- No local `terraform.tfvars` or `backend.hcl` overrides were found in bootstrap/dev.
- VPC 10.0.0.0/16, public 10.0.0.0/24 and 10.0.1.0/24, private 10.0.10.0/24 and
  10.0.11.0/24 are unchanged. Network module CIDR/NAT logic and structure are preserved.
- Dockerfile, Compose/PostgreSQL, FastAPI, Python dependencies/tests and scripts
  have no changes. Default cost_saver still creates no NAT gateways or EIPs.

Real future plans will query DescribeAvailabilityZones; these tests use synthetic
responses only. Account-specific AZ availability, service quotas, deployed behavior,
pricing and AWS Free plan eligibility were not verified. Updating configuration is
not migration of any pre-existing regional resources or state.
