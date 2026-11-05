variable "name" {
  description = "Application resource name."
  type        = string
}
variable "aws_region" {
  description = "CloudWatch logs region."
  type        = string
}
variable "environment" {
  description = "APP_ENV label."
  type        = string
}
variable "network_mode" {
  description = "cost_saver uses public task ENIs; production_like uses private task ENIs."
  type        = string
  validation {
    condition     = contains(["cost_saver", "production_like"], var.network_mode)
    error_message = "Choose cost_saver or production_like."
  }
}
variable "public_subnet_ids" {
  description = "Public subnets for cost_saver tasks."
  type        = list(string)
}
variable "private_subnet_ids" {
  description = "Private subnets for production_like tasks; require NAT or suitable endpoints."
  type        = list(string)
}
variable "security_group_id" {
  description = "ECS SG permitting port 8000 only from the ALB."
  type        = string
}
variable "target_group_arn" {
  description = "ALB IP target group ARN."
  type        = string
}
variable "execution_role_arn" {
  description = "ECS agent execution role."
  type        = string
}
variable "task_role_arn" {
  description = "Unprivileged application role."
  type        = string
}
variable "log_group_name" {
  description = "Pre-created CloudWatch application log group."
  type        = string
}
variable "container_image" {
  description = "Existing application image in the intended ECR repository, pinned tag or digest."
  type        = string
  validation {
    condition     = !endswith(var.container_image, ":latest") && (can(regex("^[^@ ]+:[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$", var.container_image)) || can(regex("^[^@ ]+@sha256:[a-f0-9]{64}$", var.container_image)))
    error_message = "Provide an explicitly tagged (not latest) image or sha256 digest."
  }
}
variable "repository_url" {
  description = "Allowed ECR repository URL."
  type        = string
}
variable "desired_count" {
  description = "Initial task count; zero is useful for a future approved image staging step."
  type        = number
  default     = 1
  validation {
    condition     = var.desired_count >= 0 && var.desired_count <= 10 && floor(var.desired_count) == var.desired_count
    error_message = "desired_count must be an integer between 0 and 10."
  }
}
variable "app_version" {
  description = "Release metadata, not used to select the image."
  type        = string
  default     = "0.1.0"
}
variable "git_sha" {
  description = "Source revision baked into runtime metadata."
  type        = string
  default     = "unknown"
}
variable "ssm_parameters" {
  description = "Environment-name to existing SSM parameter ARN; never plaintext values."
  type        = map(string)
  default     = {}
  validation {
    condition = alltrue([
      for name, arn in var.ssm_parameters : can(regex("^[A-Z][A-Z0-9_]*$", name)) &&
      !contains(["DATABASE_URL", "DATABASE_PASSWORD_FILE", "APP_ENV", "APP_VERSION", "GIT_SHA", "LOG_LEVEL"], name) &&
      can(regex("^arn:[^:]+:ssm:[^:]+:[0-9]{12}:parameter/[^*?]+$", arn))
    ])
    error_message = "Use explicit SSM ARNs and uppercase environment names; DB and built-in app settings cannot be overridden in this milestone."
  }
}
variable "tags" {
  description = "Consistent project tags."
  type        = map(string)
  default     = {}
}
