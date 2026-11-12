# Task 24A resource checklist

Rates are Task 23 Sydney list prices retrieved 2026-11-12, USD before credits/tax. Billing resources generated implicitly by AWS are listed separately. Every listed Terraform action must remain create.

| Planned address | Cost driver / deployment check |
| --- | --- |
| `module.alb.aws_lb.this` | $0.0252/hour + $0.008/LCU-hour; at least two IPv4s add $0.010/hour. HTTP80 only. |
| `module.alb.aws_lb_listener.http` | Included in ALB baseline; port80 HTTP. No credentials or private user data. |
| `module.alb.aws_lb_target_group.app` | Included in ALB; IP targets port8000; /ready matcher200. |
| `module.ecs_service.aws_ecs_cluster.this` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.ecs_service.aws_ecs_service.app` | One task: $0.0148/hour compute + $0.005/hour IPv4; rollout may temporarily double tasks. ALB-only ingress. |
| `module.ecs_service.aws_ecs_task_definition.app` | No standalone fee; X86_64, 256 CPU/512 MiB, approved digest, UID10001, empty DB settings. |
| `module.iam.aws_iam_role.execution` | No standalone fee; execution-role scope and PassRole reviewed; task role unprivileged. |
| `module.iam.aws_iam_role.task` | No standalone fee; execution-role scope and PassRole reviewed; task role unprivileged. |
| `module.iam.aws_iam_role_policy.execution` | No standalone fee; execution-role scope and PassRole reviewed; task role unprivileged. |
| `module.network.aws_default_security_group.this` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_internet_gateway.this` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_route.public_internet` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_route_table.private["ap-southeast-2a"]` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_route_table.private["ap-southeast-2b"]` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_route_table.public` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_route_table_association.private["ap-southeast-2a"]` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_route_table_association.private["ap-southeast-2b"]` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_route_table_association.public["ap-southeast-2a"]` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_route_table_association.public["ap-southeast-2b"]` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_security_group.alb` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_security_group.ecs` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_security_group.postgresql` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_subnet.private["ap-southeast-2a"]` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_subnet.private["ap-southeast-2b"]` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_subnet.public["ap-southeast-2a"]` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_subnet.public["ap-southeast-2b"]` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_vpc.this` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_vpc_security_group_egress_rule.alb_to_ecs` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_vpc_security_group_egress_rule.ecs_https` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_vpc_security_group_egress_rule.ecs_to_postgresql` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_vpc_security_group_ingress_rule.alb_https["0.0.0.0/0"]` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_vpc_security_group_ingress_rule.ecs_from_alb` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.network.aws_vpc_security_group_ingress_rule.postgresql_from_ecs` | No standalone hourly fee; verify tags and expected new dev VPC ownership. |
| `module.observability.aws_cloudwatch_log_group.app` | $0.67/GB ingestion + $0.033/GB-month storage; seven-day retention. No secret logging. |

Implicit: two absent service-linked IAM roles may be auto-created (no hourly fee); public IPv4s and task ENIs are AWS-managed. No NAT/RDS/EIP/VPC-endpoint resources. Data transfer, ECR and S3 state storage remain usage-based. A default SG is AWS-created with the VPC and adopted by Terraform.

Operating checklist: approve short duration/cost; finish source review/commit; prepare clean-commit plan; compare exact actions; obtain deployment approval; deploy; verify target health/release; monitor logs/cost; approve teardown; audit remaining billed resources.
