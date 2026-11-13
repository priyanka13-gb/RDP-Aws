# Portfolio completion and account boundary

Verified 14 November 2026 IST. The portfolio is complete for an evidence-based
interview presentation. GitHub CI is operational; cloud publishing and deployment
remain explicit human operations, not an enabled continuous-delivery pipeline.

## Verified achievements and limits

| Area | Evidence / claim boundary |
| --- | --- |
| Backend | FastAPI health/readiness/version/Prometheus endpoints, JSON request logging, optional pooled PostgreSQL readiness |
| Container | Digest-pinned Python3.12 Alpine, AMD64, UID10001, multi-stage dependency installation, no runtime pip |
| Tests | Task34 rerun: 93 unit and two real PostgreSQL16 service tests passed; guard tests included |
| Hosted CI | [Run 43487727943](https://github.com/priyanka13-gb/RDP-Aws/actions/runs/43487727943) passed at 693efb2: Ruff, unit/PG tests, nine Terraform validations/23 mock tests, Docker build, zero Trivy findings |
| ECR | Previously published immutable git-9b18a3109aa2; AMD64 child digest e86be3d8597649995145a5e1633bfc4ccf19b8ca1185127ea6720d72d2bf0be1 |
| AWS demo | Historical 34-resource Fargate/ALB deployment and teardown audited; retained summaries/history corroborate it, raw HTTP/log archives are incomplete |
| Recovery | Five local Docker scenarios passed in Task30/31; live ECS circuit-breaker rollback remains NOT VERIFIED |
| Current resources | Read-only Task34 status: zero demo tasks/services/clusters, ALBs, VPCs/ENIs, log groups and managed dev-state instances; scoped inventory is not billing data |
| Retained resources | ECR image storage and versioned S3 state remain intentionally; not a zero-cost or account-wide zero-resource claim |

Source: [historical live audit](first-deployment-teardown-audit.md),
[recovery record](incidents/local-failure-drill.md),
[Task34 results](../evidence/task34/verification.json).
Zero findings is a dated scan result, not permanent assurance. Hosted CI belongs
to the identified commit; this local documentation commit has not been pushed or
executed on GitHub. Application, Docker, Terraform and active workflows are unchanged.

## Free-plan limitation and OIDC decision

Read-only account-plan API confirms ACTIVE / FREE. AWS describes explicit identity
provider management and granular permissions as part of
[advanced features](https://aws.amazon.com/start-here/). Its
[Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/) states activation
cannot be reverted to the Free plan. This project does not activate those features,
change the account plan or provision IAM to finish a portfolio.

Observed locally: both existing AWS profiles authenticate, but IAM OIDC provider
List/Get returned AccessDenied; the proposed publishing role returned NoSuchEntity.
AccessDenied alone does not distinguish account-feature restrictions from IAM/SCP
authorization. We do not claim a service error proves that every Free-plan account
has identical IAM permissions. The confirmed account boundary and unsuccessful
provider audit are sufficient reasons to defer this feature here.

OIDC design files and inactive `.yml.example` authentication template are retained
as architectural work, not proof of federation. No JWT/STS exchange through GitHub
was tested. The manual release workflow remains workflow_dispatch-only with
publish=false by default, and the repository enablement variable is absent.
Do not set that variable, add identifier secrets, copy the auth template into active
workflows or create IAM resources as part of this completion milestone.

GitHub main has the four successful CI jobs configured as required checks and no
ruleset bypass actors. The release environment permits only main and disables
administrator bypass, but has no required reviewers; main requires zero PR
approvals and does not require up-to-date branches. These are documented
hardening gaps, not completed approval controls. They are not bypassed to enable
OIDC. Future publishing automation requires a separately reviewed security scope.

## Credentials and manual delivery

The Task34 inspection found no permanent AWS key entries in the inspected local
AWS config/credentials paths or process environment. The shared credentials file
was absent; config had no access-key fields. rdp-dev exports an expiring session
token and no AKIA permanent key. Tokens/key values were never printed or saved in
evidence. This is a scoped check, not a forensic claim about every file/back-up on
the computer. Existing CLI login caches may retain temporary session material.
Repository secrets are checked with Trivy before committing.

Use only the [temporary-credential manual ECR procedure](manual-ecr-temporary-credentials.md)
for a separately approved release. It retains clean-commit tags, fresh scans,
local endpoint checks, temporary Docker authentication, collision refusal,
digest binding and ECR child-image scan verification. It never creates a
repository or silently publishes from the GitHub workflow. No release was
executed by Task34.

## Deployment/cleanup review

The existing demo workflow still checks account/backend/workspace, approved image,
resource allowlist, ALB-only ingress, cost_saver networking, seven-day logging and
plan actions. Saved plans bind source commit/checksum/context, expire after one
hour and are consumed before apply. Deploy/cleanup require typed interactive
confirmation. Cleanup creates a fresh dev-only plan, supports reviewed partial
deployments and verifies resource removal; bootstrap/ECR are preserved.

No deploy, cleanup, apply, destroy or rollback command was run by Task34. Cleanup
is not guaranteed by a timer: an available operator, permissions and service
availability are required. A future demo needs separate deployment/teardown
approval, an independent alarm, a time/cost budget, retained evidence and a
post-cleanup billing review. Do not prune Docker volumes or delete local
PostgreSQL data. Historical cost figures are estimates, not current quotes/caps.

## Remaining work

- Optional authorized Git push/PR to publish the documentation and obtain hosted
  CI for that exact new commit. No automatic push is part of this task.
- Optional independent-review/up-to-date-branch hardening; no settings changed here.
- A future live rollback drill requires a current completed healthy deployment,
  explicit failure-injection/restoration/cleanup approval, and actual AWS evidence.
- HTTPS/domain, database hosting, load/availability testing, continuous alerting
  and enabled OIDC/CD are deferred. Do not claim production readiness, proven
  rollback, measured SLA or zero future vulnerabilities.

**Portfolio: GO for presentation. New AWS deployment / automated publishing:
not authorized and not required.**
