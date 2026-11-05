mock_provider "aws" {
  override_during = plan
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_partition" {
    defaults = { partition = "aws", dns_suffix = "amazonaws.com" }
  }
  mock_data "aws_region" {
    defaults = { region = "ap-southeast-2" }
  }
  mock_resource "aws_lb" {
    defaults = { arn = "arn:aws:elasticloadbalancing:ap-southeast-2:123456789012:loadbalancer/app/test/1234567890123456" }
  }
  mock_resource "aws_lb_target_group" {
    defaults = { arn = "arn:aws:elasticloadbalancing:ap-southeast-2:123456789012:targetgroup/test/1234567890123456" }
  }
}

run "ecr_immutability_and_retention" {
  command = plan
  module { source = "../../modules/ecr" }
  variables { name = "rdp-test" }
  assert {
    condition     = aws_ecr_repository.this.image_tag_mutability == "IMMUTABLE" && aws_ecr_repository.this.image_scanning_configuration[0].scan_on_push && one(aws_ecr_repository.this.encryption_configuration).encryption_type == "AES256" && !aws_ecr_repository.this.force_delete
    error_message = "Repository must be immutable, encrypted, scanned and protected from force deletion."
  }
  assert {
    condition     = jsondecode(aws_ecr_lifecycle_policy.this.policy).rules[0].selection.countNumber == 20
    error_message = "Expected 20-image retention."
  }
}

run "alb_ip_targets" {
  command = plan
  module { source = "../../modules/alb" }
  variables {
    name              = "aws-resilient-delivery-platform-dev"
    vpc_id            = "vpc-11111111"
    public_subnet_ids = ["subnet-11111111", "subnet-22222222"]
    security_group_id = "sg-11111111"
  }
  assert {
    condition     = !aws_lb.this.internal && length(aws_lb.this.subnets) == 2 && aws_lb_listener.http.port == 80 && aws_lb_listener.http.protocol == "HTTP"
    error_message = "ALB must expose the temporary HTTP demo across two public subnets."
  }
  assert {
    condition     = aws_lb_target_group.app.target_type == "ip" && aws_lb_target_group.app.port == 8000 && aws_lb_target_group.app.health_check[0].path == "/ready" && aws_lb_target_group.app.health_check[0].matcher == "200" && aws_lb_target_group.app.health_check[0].healthy_threshold == 2 && aws_lb_target_group.app.health_check[0].unhealthy_threshold == 3
    error_message = "ALB targets/readiness settings must match FastAPI."
  }
}

run "scoped_execution_role" {
  command = plan
  module { source = "../../modules/iam" }
  variables {
    name           = "rdp-test"
    repository_arn = "arn:aws:ecr:ap-southeast-2:123456789012:repository/rdp-test"
    log_group_arn  = "arn:aws:logs:ap-southeast-2:123456789012:log-group:/ecs/rdp-test"
  }
  assert {
    condition     = length(jsondecode(aws_iam_role_policy.execution.policy).Statement) == 3 && jsondecode(aws_iam_role_policy.execution.policy).Statement[1].Resource == [var.repository_arn] && jsondecode(aws_iam_role_policy.execution.policy).Statement[2].Resource == ["${var.log_group_arn}:log-stream:*"]
    error_message = "Default execution role must only pull intended images and write intended logs, with no SSM."
  }
  assert {
    condition     = jsondecode(aws_iam_role_policy.execution.policy).Statement[0].Action == ["ecr:GetAuthorizationToken"] && jsondecode(aws_iam_role_policy.execution.policy).Statement[0].Resource == ["*"] && aws_iam_role.task.name != aws_iam_role.execution.name
    error_message = "Only ECR token acquisition needs global resource scope; roles must be separate."
  }
  assert {
    condition     = jsondecode(aws_iam_role.task.assume_role_policy).Statement[0].Principal.Service == "ecs-tasks.amazonaws.com" && jsondecode(aws_iam_role.task.assume_role_policy).Statement[0].Condition.StringEquals["aws:SourceAccount"] == "123456789012"
    error_message = "Task trust must be scoped to ECS and the current account."
  }
}

run "optional_ssm_is_scoped" {
  command = plan
  module { source = "../../modules/iam" }
  variables {
    name               = "rdp-test"
    repository_arn     = "arn:aws:ecr:ap-southeast-2:123456789012:repository/rdp-test"
    log_group_arn      = "arn:aws:logs:ap-southeast-2:123456789012:log-group:/ecs/rdp-test"
    ssm_parameter_arns = ["arn:aws:ssm:ap-southeast-2:123456789012:parameter/rdp/test/setting"]
    ssm_kms_key_arns   = ["arn:aws:kms:ap-southeast-2:123456789012:key/00000000-0000-0000-0000-000000000001"]
  }
  assert {
    condition     = length(jsondecode(aws_iam_role_policy.execution.policy).Statement) == 5 && toset(jsondecode(aws_iam_role_policy.execution.policy).Statement[3].Resource) == var.ssm_parameter_arns && toset(jsondecode(aws_iam_role_policy.execution.policy).Statement[4].Resource) == var.ssm_kms_key_arns
    error_message = "Optional SSM and KMS permissions must be explicitly scoped."
  }
}

run "log_retention" {
  command = plan
  module { source = "../../modules/observability" }
  variables { name = "rdp-test" }
  assert {
    condition     = aws_cloudwatch_log_group.app.retention_in_days == 7 && aws_cloudwatch_log_group.app.name == "/ecs/rdp-test"
    error_message = "Log group must use seven-day retention."
  }
}

run "http_demo_network_boundaries" {
  command = plan
  module { source = "../../modules/network" }
  variables {
    availability_zones = ["ap-southeast-2a", "ap-southeast-2b"]
    alb_ingress_port   = 80
  }
  override_resource {
    override_during = plan
    target          = aws_security_group.alb
    values          = { id = "sg-11111111" }
  }
  override_resource {
    override_during = plan
    target          = aws_security_group.ecs
    values          = { id = "sg-22222222" }
  }
  override_resource {
    override_during = plan
    target          = aws_security_group.postgresql
    values          = { id = "sg-33333333" }
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.alb_https["0.0.0.0/0"].from_port == 80 && aws_vpc_security_group_ingress_rule.ecs_from_alb.referenced_security_group_id == "sg-11111111" && aws_vpc_security_group_ingress_rule.ecs_from_alb.cidr_ipv4 == null && aws_vpc_security_group_ingress_rule.ecs_from_alb.from_port == 8000 && aws_vpc_security_group_ingress_rule.ecs_from_alb.to_port == 8000
    error_message = "Only the ALB may reach the ECS application port; never public CIDRs."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.postgresql_from_ecs.referenced_security_group_id == "sg-22222222" && aws_vpc_security_group_ingress_rule.postgresql_from_ecs.cidr_ipv4 == null && length(aws_nat_gateway.this) == 0 && length(aws_eip.nat) == 0
    error_message = "Preserve private DB boundaries and no-NAT defaults."
  }
}
