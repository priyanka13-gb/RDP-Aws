# Terraform network foundation verification

## Tooling

- Portable Terraform **1.13.5**, Windows AMD64, stored in ignored `.tools/terraform`.
- Binary downloaded from HashiCorp's release server and checked against the published
  SHA-256 checksum. No system-wide installation or PATH changes.
- AWS provider **6.71.0**, constraint `~> 6.0`; dev initialization verified the
  HashiCorp signature. Provider versions and release checksums are retained in
  both root and module `.terraform.lock.hcl` files.

## Actual results

| Check | Result |
| --- | --- |
| `terraform fmt -recursive` | Formatted module variables |
| `terraform fmt -recursive -check` | Passed, exit 0 |
| Dev: `terraform init -backend=false -input=false` | Successfully initialized |
| Dev: `terraform validate` | Success: configuration is valid |
| Module: `terraform init -backend=false -input=false` with local provider directory | Successfully initialized |
| Module: `terraform validate` | Success: configuration is valid |
| Module: `terraform test` | **5 passed, 0 failed**, exit 0 |
| `git diff --check` | Passed; Git noted only its existing CRLF conversion policy for .gitignore |
| Diff of app, tests, pyproject.toml, compose.yaml, .dockerignore and scripts | No changes |

The module reused the provider downloaded by dev with
`-plugin-dir=../../envs/dev/.terraform/providers`. Initial sandbox registry access
and provider copying were blocked; reruns with the required access succeeded.
The first local-provider init generated a Windows-only lockfile warning. It was
replaced with the dev root's authenticated release-checksum lockfile; a subsequent
`init -backend=false -lockfile=readonly` succeeded without that warning.

Mock test cases:

1. `cost_saver_has_no_nat`: zero NATs, EIPs, and private default routes; two public
   and two private subnets; two private route tables; CIDR and ingress constraints.
2. `per_az_nat`: two NAT gateways, two EIPs, two private default routes.
3. `single_nat`: one NAT in the first AZ, two private default routes.
4. `reject_nat_in_cost_saver`: contradictory NAT setting rejected.
5. `require_explicit_production_nat`: production_like without NAT selection rejected.

All Terraform test runs use a **mock provider** and **command = plan**. No real AWS
plan, apply, destroy, IAM access-key creation, or AWS resource creation was performed.
Terraform's test teardown message refers to the mock test framework, not deployed resources.

## Remaining boundaries

No unresolved syntax, initialization, validation, or mock-test failures remain.
Live AWS account permissions, quotas, AZ availability, connectivity, and deployed
security behavior have not been checked. No billable resources were created.
Private ECS outbound dependencies remain a future design decision in cost_saver:
the network intentionally contains neither NAT nor VPC endpoints by default.
Current Mumbai pricing must be reviewed before any explicit NAT deployment.
