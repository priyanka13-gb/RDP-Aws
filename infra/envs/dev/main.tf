data "aws_availability_zones" "available" {
  state = "available"
  filter {
    name   = "zone-type"
    values = ["availability-zone"]
  }
  lifecycle {
    postcondition {
      condition     = length(self.names) >= 2 && alltrue([for az in var.availability_zones : contains(self.names, az)])
      error_message = "The selected region must expose at least two available standard AZs, including any pinned AZs."
    }
  }
}

locals {
  availability_zones = length(var.availability_zones) > 0 ? var.availability_zones : slice(sort(data.aws_availability_zones.available.names), 0, min(2, length(data.aws_availability_zones.available.names)))
  name               = "aws-resilient-delivery-platform-${var.environment}"
  tags = merge(var.tags, {
    Project     = "aws-resilient-delivery-platform"
    Environment = var.environment
    ManagedBy   = "Terraform"
    NetworkMode = var.network_mode
  })
}

module "network" {
  source = "../../modules/network"

  project_name       = "aws-resilient-delivery-platform"
  environment        = var.environment
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = local.availability_zones
  network_mode       = var.network_mode
  nat_gateway_mode   = var.nat_gateway_mode
  alb_ingress_cidrs  = var.alb_ingress_cidrs
  alb_ingress_port   = 80
  tags               = var.tags
}

# Owned exclusively by infra/envs/ecr; dev only reads repository metadata.
data "aws_ecr_repository" "app" {
  name = local.name
}

module "observability" {
  source = "../../modules/observability"
  name   = local.name
  tags   = local.tags
}

module "iam" {
  source             = "../../modules/iam"
  name               = local.name
  repository_arn     = data.aws_ecr_repository.app.arn
  log_group_arn      = module.observability.log_group_arn
  ssm_parameter_arns = toset(values(var.ssm_parameters))
  ssm_kms_key_arns   = var.ssm_kms_key_arns
  tags               = local.tags
}

module "alb" {
  source            = "../../modules/alb"
  name              = local.name
  vpc_id            = module.network.vpc_id
  public_subnet_ids = module.network.public_subnet_ids
  security_group_id = module.network.security_group_ids.alb
  tags              = local.tags
}

module "ecs_service" {
  source             = "../../modules/ecs_service"
  name               = local.name
  aws_region         = var.aws_region
  environment        = var.environment
  network_mode       = var.network_mode
  public_subnet_ids  = module.network.public_subnet_ids
  private_subnet_ids = module.network.private_subnet_ids
  security_group_id  = module.network.security_group_ids.ecs
  target_group_arn   = module.alb.target_group_arn
  execution_role_arn = module.iam.execution_role_arn
  task_role_arn      = module.iam.task_role_arn
  log_group_name     = module.observability.log_group_name
  repository_url     = data.aws_ecr_repository.app.repository_url
  container_image    = var.image_digest != null ? "${data.aws_ecr_repository.app.repository_url}@${var.image_digest}" : var.container_image
  desired_count      = var.desired_count
  app_version        = var.app_version
  git_sha            = var.git_sha
  ssm_parameters     = var.ssm_parameters
  tags               = local.tags
  # The listener must associate the target group with the ALB before service creation.
  depends_on = [module.network, module.alb]
}
