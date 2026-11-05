# Select rdp-dev via AWS_PROFILE; never put credentials in Terraform.
provider "aws" {
  region = var.aws_region
}
locals {
  tags = merge(var.tags, {
    Project     = "aws-resilient-delivery-platform"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Component   = "ecr"
  })
}
module "ecr" {
  source = "../../modules/ecr"
  name   = "aws-resilient-delivery-platform-${var.environment}"
  tags   = local.tags
}
