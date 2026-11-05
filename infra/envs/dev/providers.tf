provider "aws" {
  region = var.aws_region

  # Use the standard AWS credential chain for future authorized plans/deployments.
  # init/validate require no AWS credentials and make no AWS resource changes.
  default_tags {
    tags = {
      Project     = "aws-resilient-delivery-platform"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}
