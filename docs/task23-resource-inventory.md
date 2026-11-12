# Task 23 planned resource inventory

All entries are create actions. No replacements, updates or deletions. The default SG entry adopts and clears rules on the new VPC default group; AWS itself creates that group with the VPC. Two service-linked IAM roles may additionally be created implicitly by AWS and are not represented as Terraform-managed resources below.

| Address | Type |
| --- | --- |
| `module.alb.aws_lb.this` | aws_lb |
| `module.alb.aws_lb_listener.http` | aws_lb_listener |
| `module.alb.aws_lb_target_group.app` | aws_lb_target_group |
| `module.ecs_service.aws_ecs_cluster.this` | aws_ecs_cluster |
| `module.ecs_service.aws_ecs_service.app` | aws_ecs_service |
| `module.ecs_service.aws_ecs_task_definition.app` | aws_ecs_task_definition |
| `module.iam.aws_iam_role.execution` | aws_iam_role |
| `module.iam.aws_iam_role.task` | aws_iam_role |
| `module.iam.aws_iam_role_policy.execution` | aws_iam_role_policy |
| `module.network.aws_default_security_group.this` | aws_default_security_group |
| `module.network.aws_internet_gateway.this` | aws_internet_gateway |
| `module.network.aws_route.public_internet` | aws_route |
| `module.network.aws_route_table.private["ap-southeast-2a"]` | aws_route_table |
| `module.network.aws_route_table.private["ap-southeast-2b"]` | aws_route_table |
| `module.network.aws_route_table.public` | aws_route_table |
| `module.network.aws_route_table_association.private["ap-southeast-2a"]` | aws_route_table_association |
| `module.network.aws_route_table_association.private["ap-southeast-2b"]` | aws_route_table_association |
| `module.network.aws_route_table_association.public["ap-southeast-2a"]` | aws_route_table_association |
| `module.network.aws_route_table_association.public["ap-southeast-2b"]` | aws_route_table_association |
| `module.network.aws_security_group.alb` | aws_security_group |
| `module.network.aws_security_group.ecs` | aws_security_group |
| `module.network.aws_security_group.postgresql` | aws_security_group |
| `module.network.aws_subnet.private["ap-southeast-2a"]` | aws_subnet |
| `module.network.aws_subnet.private["ap-southeast-2b"]` | aws_subnet |
| `module.network.aws_subnet.public["ap-southeast-2a"]` | aws_subnet |
| `module.network.aws_subnet.public["ap-southeast-2b"]` | aws_subnet |
| `module.network.aws_vpc.this` | aws_vpc |
| `module.network.aws_vpc_security_group_egress_rule.alb_to_ecs` | aws_vpc_security_group_egress_rule |
| `module.network.aws_vpc_security_group_egress_rule.ecs_https` | aws_vpc_security_group_egress_rule |
| `module.network.aws_vpc_security_group_egress_rule.ecs_to_postgresql` | aws_vpc_security_group_egress_rule |
| `module.network.aws_vpc_security_group_ingress_rule.alb_https["0.0.0.0/0"]` | aws_vpc_security_group_ingress_rule |
| `module.network.aws_vpc_security_group_ingress_rule.ecs_from_alb` | aws_vpc_security_group_ingress_rule |
| `module.network.aws_vpc_security_group_ingress_rule.postgresql_from_ecs` | aws_vpc_security_group_ingress_rule |
| `module.observability.aws_cloudwatch_log_group.app` | aws_cloudwatch_log_group |
