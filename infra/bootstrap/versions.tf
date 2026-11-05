terraform {
  required_version = ">= 1.10.0, < 2.0.0"
  # Intentionally local state. Do not point this stack at the bucket it creates.
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
