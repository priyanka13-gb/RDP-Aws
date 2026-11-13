# First AWS deployment and teardown audit

Audit date: 2026-11-13. **Deployment VERIFIED. Teardown VERIFIED.**

This is an operational audit of recorded execution, corroborated by AWS-managed
state history and CloudTrail. The application is no longer deployed, so endpoint
health cannot be retested live. No apply/destroy, resource creation, state write,
Git commit/push or architecture change was performed during this audit.

## Evidence and verdict

| Question | Evidence | Assessment |
| --- | --- | --- |
| Did the dev infrastructure exist? | Versioned S3 dev state contained all 34 managed resources, including ECS service, ALB and log group; CloudTrail records successful service/ALB/VPC creation | VERIFIED |
| Did Terraform deployment complete? | `.tools/demo/deploy.json`: consumed=true, 34 create actions, result=apply completed; the committed script writes that marker only after Terraform returns success | VERIFIED with AWS history corroboration |
| Was an ECS task running the approved release? | Local verifier success record plus source at commit `14c4d49b84aaa7b21187bc6c3cae28c659f6dbaf`; it requires stable service, exactly one running task and matching child image digest before recording success | VERIFIED from recorded verifier execution |
| Were targets and endpoints healthy? | Verification at 15:31:59 IST reports target_health=healthy and http_endpoints=passed; verifier requires healthy ALB targets, HTTP200 and expected health/readiness/version/metrics contents | VERIFIED from retained summary, not raw response archive |
| Were application logs present? | Same verification sampled 86 recent CloudWatch events; verifier requires nonempty logs and rejects a traceback in its sample | VERIFIED from retained summary; sample is not complete error history |
| Did cleanup finish? | `.tools/demo/cleanup.json`: 34 delete actions, consumed=true, result=apply completed; CloudTrail confirms deletes and latest S3 state is empty | VERIFIED |
| Are resources absent now? | Fresh AWS/remote-state inventory: zero demo ECS cluster/service/tasks, ALB/target group, VPC/subnets/routes/SGs/IGW/ENIs, tagged EIPs and log groups; dev task/execution roles absent | VERIFIED within reviewed dev scope |

Approved image: `sha256:e86be3d8597649995145a5e1633bfc4ccf19b8ca1185127ea6720d72d2bf0be1`.
The verifier recorded this same child digest. Versioned deployed state records
ECS desired_count=1. Current remote dev state has **zero resources**, serial 5;
the empty S3 state object still exists, which is normal after teardown.

## Timeline - 13 November 2026, IST (UTC+05:30)

| Time | Evidence |
| --- | --- |
| 14:19:15 | CloudTrail: demo VPC created, no error |
| 14:19:25 | CloudTrail: application ALB created, no error |
| 14:21:53 | S3 state serial1: intermediate deployment, 30 managed resources |
| 14:22:08 | CloudTrail: ECS service created, no error |
| 14:24:04 | S3 state serial3: all 34 resources, ECS desired count1 |
| 15:31:59 | Local verification: approved task release, healthy targets/endpoints, 86 log events |
| 15:35:01 | Cleanup plan record created, 34 delete actions |
| 15:36:10 | CloudTrail: ECS service deletion, no error |
| 15:38:48 | CloudTrail: ALB deletion, no error |
| 15:39:10 | CloudTrail: remembered demo VPC deletion, no error |
| 15:39:11 | S3 state serial5: zero managed resources |

VPC create/delete events were correlated with the remembered demo VPC ID in memory;
identifiers are excluded from the published evidence. ECS and ALB events match
the application names. CloudTrail confirms management operations, not HTTP health.

## Missing proof and limits

- Raw endpoint-by-endpoint HTTP status/body transcripts and separate request
  timestamps were not preserved. The success summary and exact committed verifier
  behavior provide the retained proof.
- Full ECS task/ALB target-health response snapshots were not retained beyond the
  summary. Current APIs cannot return a live healthy task after teardown.
- Application log bodies and streams were removed with the CloudWatch group.
  The retained verifier records the successful 86-event sample, not those bodies.
- Literal Terraform terminal `Apply complete!`/`Destroy complete!` output was not
  archived. The helper captures/discards output; its success markers are
  corroborated by resource history and the empty final remote state.
- Local summaries are unsigned; this is operational evidence, not a tamper-proof
  forensic attestation. Prepared-plan evidence and local Docker test logs were
  not counted as proof of live AWS health.
- The audit covers the named/tagged demo and remembered VPC, not every unrelated
  resource in the account. It is not proof that the account has zero charges.
  Retained ECR images, S3 versions and account-wide service-linked roles can remain.

No missing item requires another deployment solely to establish that the first
one occurred. For stronger interview evidence, capture sanitized per-endpoint
responses, task/target state and a small log sample, plus Terraform completion
output during the next separately approved demo, before cleaning up. Keep raw
state/ARN/account data private; never publish credentials or user data.

## Recommended next action

Keep the dev stack absent. Preserve this report and sanitized evidence, then
check AWS Billing/credit usage once delayed charges settle. Reuse the normal
prepare/deploy/verify/cleanup workflow only when another interview needs a live
endpoint. No redeployment, cleanup or paid audit infrastructure is required now.

Evidence: [sanitized audit](../evidence/task27/audit.json),
[AWS state/CloudTrail history](../evidence/task27/aws-history.json),
[current inventory](../evidence/task27/current-status.json),
[remaining resource checks](../evidence/task27/remaining-resources.json),
[local record hashes](../evidence/task27/local-evidence.json),
[committed verifier checks](../evidence/task27/verifier-source-check.json).

Raw historical state snapshots were read only into ignored `.tools/task27/`
private files for this audit. They contain account-specific metadata and must
not be staged or shared. Task 31 reviewed this historical report for a local
documentation commit; its timestamps and evidence limits remain unchanged.
