# Synthetic account/ARN fixtures only; all runs use mock plan, never AWS.
mock_provider "aws" {
  override_during = plan
  mock_resource "aws_ecs_cluster" {
    defaults = { id = "arn:aws:ecs:ap-southeast-2:123456789012:cluster/test" }
  }
  mock_resource "aws_ecs_task_definition" {
    defaults = { arn = "arn:aws:ecs:ap-southeast-2:123456789012:task-definition/test:1" }
  }
}

variables {
  name               = "rdp-test"
  aws_region         = "ap-southeast-2"
  environment        = "test"
  network_mode       = "cost_saver"
  public_subnet_ids  = ["subnet-11111111", "subnet-22222222"]
  private_subnet_ids = ["subnet-33333333", "subnet-44444444"]
  security_group_id  = "sg-11111111"
  target_group_arn   = "arn:aws:elasticloadbalancing:ap-southeast-2:123456789012:targetgroup/test/1234567890123456"
  execution_role_arn = "arn:aws:iam::123456789012:role/test-execution"
  task_role_arn      = "arn:aws:iam::123456789012:role/test-task"
  log_group_name     = "/ecs/rdp-test"
  repository_url     = "123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/rdp-test"
  container_image    = "123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/rdp-test:release-test"
}

run "public_demo_task" {
  command = plan
  module { source = "../../modules/ecs_service" }
  assert {
    condition     = aws_ecs_service.app.network_configuration[0].assign_public_ip && toset(aws_ecs_service.app.network_configuration[0].subnets) == toset(var.public_subnet_ids) && toset(aws_ecs_service.app.network_configuration[0].security_groups) == toset([var.security_group_id])
    error_message = "cost_saver must use the public subnets, public IP and ECS-only SG."
  }
  assert {
    condition     = aws_ecs_service.app.deployment_circuit_breaker[0].enable && aws_ecs_service.app.deployment_circuit_breaker[0].rollback && aws_ecs_service.app.health_check_grace_period_seconds == 60 && aws_ecs_service.app.desired_count == 1
    error_message = "Demo count, health grace or deployment rollback changed."
  }
  assert {
    condition     = aws_ecs_task_definition.app.cpu == "256" && aws_ecs_task_definition.app.memory == "512" && aws_ecs_task_definition.app.network_mode == "awsvpc" && aws_ecs_task_definition.app.runtime_platform[0].operating_system_family == "LINUX"
    error_message = "Task sizing/platform must match the intended Fargate configuration."
  }
  assert {
    condition     = jsondecode(aws_ecs_task_definition.app.container_definitions)[0].portMappings[0].containerPort == 8000 && jsondecode(aws_ecs_task_definition.app.container_definitions)[0].user == "10001:10001" && !can(jsondecode(aws_ecs_task_definition.app.container_definitions)[0].command)
    error_message = "Preserve the image user, port and Uvicorn CMD."
  }
  assert {
    condition     = alltrue([for entry in jsondecode(aws_ecs_task_definition.app.container_definitions)[0].environment : entry.value == "" if startswith(entry.name, "DATABASE_")]) && length(jsondecode(aws_ecs_task_definition.app.container_definitions)[0].secrets) == 0
    error_message = "Initial ECS task must use database-optional mode and no secrets."
  }
  assert {
    condition     = jsondecode(aws_ecs_task_definition.app.container_definitions)[0].logConfiguration.options["awslogs-group"] == var.log_group_name && strcontains(join(" ", jsondecode(aws_ecs_task_definition.app.container_definitions)[0].healthCheck.command), "127.0.0.1:8000/health")
    error_message = "Task logs and liveness endpoint must match the app."
  }
}

run "private_production_task" {
  command = plan
  module { source = "../../modules/ecs_service" }
  variables { network_mode = "production_like" }
  assert {
    condition     = !aws_ecs_service.app.network_configuration[0].assign_public_ip && toset(aws_ecs_service.app.network_configuration[0].subnets) == toset(var.private_subnet_ids)
    error_message = "production_like must select private subnets without public IPs."
  }
}

run "reject_wrong_repository" {
  command = plan
  module { source = "../../modules/ecs_service" }
  variables { container_image = "123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/other:release-test" }
  expect_failures = [aws_ecs_task_definition.app]
}

run "reject_database_override" {
  command = plan
  module { source = "../../modules/ecs_service" }
  variables {
    ssm_parameters = { DATABASE_URL = "arn:aws:ssm:ap-southeast-2:123456789012:parameter/test/database" }
  }
  expect_failures = [var.ssm_parameters]
}

run "reject_latest_tag" {
  command = plan
  module { source = "../../modules/ecs_service" }
  variables { container_image = "123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/rdp-test:latest" }
  expect_failures = [var.container_image]
}

run "reject_malformed_digest" {
  command = plan
  module { source = "../../modules/ecs_service" }
  variables { container_image = "123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/rdp-test@sha256:abcd" }
  expect_failures = [var.container_image]
}
