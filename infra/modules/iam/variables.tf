variable "name" {
  description = "Role name prefix."
  type        = string
}
variable "repository_arn" {
  description = "Only ECR repository the execution role can pull from."
  type        = string
}
variable "log_group_arn" {
  description = "Only CloudWatch log group the execution role can write to."
  type        = string
}
variable "ssm_parameter_arns" {
  description = "Explicit parameter allowlist; empty disables SSM permissions."
  type        = set(string)
  default     = []
  validation {
    condition     = alltrue([for arn in var.ssm_parameter_arns : can(regex("^arn:[^:]+:ssm:[^:]+:[0-9]{12}:parameter/[^*?]+$", arn))])
    error_message = "Use complete, explicitly scoped SSM parameter ARNs without wildcards."
  }
}
variable "ssm_kms_key_arns" {
  description = "Optional customer-managed KMS keys used by the allowed parameters."
  type        = set(string)
  default     = []
  validation {
    condition     = alltrue([for arn in var.ssm_kms_key_arns : can(regex("^arn:[^:]+:kms:[^:]+:[0-9]{12}:key/[^*?]+$", arn))])
    error_message = "Use complete KMS key ARNs without wildcards."
  }
}
variable "tags" {
  description = "Consistent project tags."
  type        = map(string)
  default     = {}
}
