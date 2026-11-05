# Teardown and cost audit

This procedure is separate from deployment. No teardown commands were executed in
Task 8. Every deletion needs explicit authorization and a reviewed destruction plan.
Do not delete local Docker/PostgreSQL volumes, unrelated VPCs, or account-managed roles.

## Cost exposure before teardown

| Component | Expected cost driver |
| --- | --- |
| Fargate | One 0.25 vCPU / 0.5 GiB task while running; rollout can temporarily run two |
| ALB | Running hours and capacity units, including periods with zero tasks |
| Public IPv4 | ALB addresses and public task addresses |
| ECR | Stored image layers and applicable transfer/scan usage |
| CloudWatch | Log ingestion and storage; configured retention is seven days |
| S3 state | Requests and storage, including retained historical versions |
| Network traffic | Applicable outbound/cross-AZ data transfer |
| Optional future features | NAT hourly/data/IP charges, RDS, endpoints, advanced SSM, customer-managed KMS |

Current defaults create no NAT gateways/EIPs, RDS instances, interface endpoints or
customer-managed KMS keys. cost_saver is not zero cost. USD 120 credits were observed
on 5 November 2026; do not treat that balance as a budget or a monthly-cost estimate.
Use current Sydney rates and actual runtime/traffic for an estimate before approval.

## Controlled teardown procedure

1. Confirm the existing profile, Sydney region, default workspace and exact dev
   backend. Record intended project resources privately; do not publish state or IDs.
2. Securely back up dev, ECR and bootstrap state and any logs/images needed for recovery.
   Confirm backup readability. Terraform destruction will remove the project's log
   group; seven-day retention does not protect it from deletion.
3. If authorized to stop service first, set desired_count=0 through a reviewed Terraform
   plan and apply. This stops task usage; it does not stop ALB/IP or storage usage.
4. Preserve ECR and its images during dev teardown: `infra/envs/ecr` owns them
   separately. A populated ECR repository does not block dev destruction. Once all
   consumers and rollback requirements are retired, separately approve ECR image
   cleanup and an ECR-root destruction plan. ECR has force_delete=false, so that
   separate destruction requires an empty repository. Never use account-wide cleanup.
5. Generate a fresh dev destruction plan with `terraform -chdir=infra/envs/dev plan
   -destroy -out=teardown.tfplan` (one command on one line). Review every deletion and
   obtain approval before applying the saved plan. Regenerate if intervening changes
   make it stale. Never run an unreviewed destroy or bypass locks.
6. Retain the bootstrap state bucket and local bootstrap state. Its prevent_destroy
   protection is intentional. Do not remove the protection or run bootstrap destroy.
   Eventual state-bucket decommissioning needs a separate retention/recovery decision.
7. If deletion fails due to dependencies or a nonempty repository, inspect and resolve
   the exact resource. Do not remove state entries to hide a failed deletion. Preserve
   remaining state and investigate any service-managed resources still releasing.

## Read-only cost audit

Before and after teardown, inspect only project resources in Sydney using ECS
list/describe services and tasks, ELB describe-load-balancers/target-groups, EC2
describe-network-interfaces/addresses/nat-gateways/vpc-endpoints, ECR describe-
repositories/images, CloudWatch Logs describe-log-groups and S3 bucket/version
metadata. Use counts and tags in shared reports; omit account IDs and credentials.

Confirm no running project tasks, ALBs, chargeable public addresses, NAT gateways,
endpoints or unexpected RDS resources remain. Check ECR/log remnants and retain the
state bucket deliberately. Do not delete service-linked roles or the pre-existing
VPC merely because they are visible. Check other regions only if prior deployments
used them; this review did not inventory all account resources globally.

In Billing, review current credit balance, usage by service/region and available
project tags. Distinguish gross usage from credits and net charges. Recheck after
billing data refreshes: an empty resource list does not erase past usage or guarantee
a zero bill. No paid billing API or new budget/alert is required for this read-only
procedure. If monitoring or a budget is desired, request separate authorization.

AWS documents that the [Free plan ends at six months or credit exhaustion](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier.html),
whichever occurs first. Do not upgrade the plan as a troubleshooting step.
