terraform {
  required_version = ">= 1.10.0, < 2.0.0"
  backend "s3" {
    bucket       = "rdp-tfstate-sydney-be4bb3dfae"
    key          = "aws-resilient-delivery-platform/ecr/terraform.tfstate"
    region       = "ap-southeast-2"
    encrypt      = true
    use_lockfile = true
  }
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}
