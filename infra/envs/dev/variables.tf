variable "network_mode" {
  description = "cost_saver by default; production_like requires explicit billable NAT selection."
  type        = string
  default     = "cost_saver"
}

variable "nat_gateway_mode" {
  description = "none by default; single or per_az only with production_like."
  type        = string
  default     = "none"
}

variable "availability_zones" {
  description = "Optional ordered pair of AZs; empty selects the first two sorted available standard AZs in aws_region."
  type        = list(string)
  default     = []
  nullable    = false

  validation {
    condition     = (length(var.availability_zones) == 0 || (length(var.availability_zones) == 2 && length(distinct(var.availability_zones)) == 2)) && alltrue([for az in var.availability_zones : can(regex("^${var.aws_region}[a-z]$", az))])
    error_message = "Leave AZs empty for discovery or supply exactly two distinct standard AZ names in aws_region."
  }
}

variable "alb_ingress_cidrs" {
  description = "Demo HTTP ALB client ranges; narrow to trusted test ranges where possible."
  type        = set(string)
  default     = ["0.0.0.0/0"]
}

variable "tags" {
  description = "Optional additional ownership or cost allocation tags."
  type        = map(string)
  default     = {}
}

variable "aws_region" {
  description = "AWS deployment region; AZs are discovered dynamically unless explicitly pinned."
  type        = string
  default     = "ap-southeast-2"
}

variable "environment" {
  description = "Environment suffix used consistently for resources and app metadata."
  type        = string
  default     = "dev"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,11}$", var.environment))
    error_message = "Use a lowercase environment name of 1-12 characters."
  }
}

variable "container_image" {
  description = "Required existing ECR image URI with immutable release tag or digest; never latest."
  type        = string
  default     = null
}

variable "image_digest" {
  description = "Optional immutable child-image digest; resolves against the separately managed ECR repository and takes precedence over container_image."
  type        = string
  default     = null
  validation {
    condition     = var.image_digest == null || can(regex("^sha256:[a-f0-9]{64}$", var.image_digest))
    error_message = "Use a full sha256 image digest."
  }
}

variable "desired_count" {
  description = "Initial number of tasks; use zero only for an approved image staging deployment."
  type        = number
  default     = 1
}

variable "enable_rds" {
  description = "Reserved for the separate RDS milestone; must stay false."
  type        = bool
  default     = false
  validation {
    condition     = !var.enable_rds
    error_message = "RDS is not implemented in this milestone. Keep enable_rds=false."
  }
}

variable "app_version" {
  description = "APP_VERSION endpoint value."
  type        = string
  default     = "0.1.0"
}

variable "git_sha" {
  description = "GIT_SHA endpoint value."
  type        = string
  default     = "unknown"
}

variable "enable_ssm_parameters" {
  description = "Explicitly opt in to existing SSM parameter injection and scoped read permissions."
  type        = bool
  default     = false
}

variable "ssm_parameters" {
  description = "Non-DB environment variable names mapped to existing SSM parameter ARNs, not values."
  type        = map(string)
  default     = {}
  validation {
    condition     = var.enable_ssm_parameters || length(var.ssm_parameters) == 0
    error_message = "Set enable_ssm_parameters=true before supplying parameter ARNs."
  }
}

variable "ssm_kms_key_arns" {
  description = "Optional explicit customer-managed KMS keys for the SSM parameters."
  type        = set(string)
  default     = []
  validation {
    condition     = length(var.ssm_kms_key_arns) == 0 || (var.enable_ssm_parameters && length(var.ssm_parameters) > 0)
    error_message = "KMS decrypt permission requires enabled, explicitly listed SSM parameters."
  }
}
