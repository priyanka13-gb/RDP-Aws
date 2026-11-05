resource "aws_ecs_cluster" "this" {
  name = var.name
  tags = var.tags
}

resource "aws_ecs_task_definition" "app" {
  family                   = var.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([{
    name         = "app", image = var.container_image, essential = true
    user         = "10001:10001"
    portMappings = [{ containerPort = 8000, hostPort = 8000, protocol = "tcp" }]
    # Use the image's exec-form Uvicorn CMD unchanged. No Compose hostname or mounts.
    environment = [
      { name = "APP_ENV", value = var.environment },
      { name = "APP_VERSION", value = var.app_version },
      { name = "GIT_SHA", value = var.git_sha },
      { name = "LOG_LEVEL", value = "INFO" },
      { name = "DATABASE_URL", value = "" },
      { name = "DATABASE_PASSWORD_FILE", value = "" }
    ]
    secrets = [for name, arn in var.ssm_parameters : { name = name, valueFrom = arn }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group = var.log_group_name, awslogs-region = var.aws_region, awslogs-stream-prefix = "app"
      }
    }
    healthCheck = {
      command     = ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).close()"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 30
    }
  }])
  tags = var.tags
  lifecycle {
    precondition {
      condition     = startswith(var.container_image, "${var.repository_url}:") || startswith(var.container_image, "${var.repository_url}@sha256:")
      error_message = "container_image must belong to this stack's ECR repository."
    }
  }
}

resource "aws_ecs_service" "app" {
  name                               = var.name
  cluster                            = aws_ecs_cluster.this.id
  task_definition                    = aws_ecs_task_definition.app.arn
  desired_count                      = var.desired_count
  launch_type                        = "FARGATE"
  platform_version                   = "1.4.0"
  health_check_grace_period_seconds  = 60
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  wait_for_steady_state              = true
  enable_execute_command             = false
  enable_ecs_managed_tags            = true
  propagate_tags                     = "SERVICE"
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  network_configuration {
    subnets          = var.network_mode == "cost_saver" ? var.public_subnet_ids : var.private_subnet_ids
    assign_public_ip = var.network_mode == "cost_saver"
    security_groups  = [var.security_group_id]
  }
  load_balancer {
    target_group_arn = var.target_group_arn
    container_name   = "app"
    container_port   = 8000
  }
  tags = var.tags
}
