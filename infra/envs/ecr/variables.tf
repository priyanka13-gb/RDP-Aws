variable "aws_region" {
  description = "Repository region; backend region is configured independently."
  type        = string
  default     = "ap-southeast-2"
}
variable "environment" {
  description = "Repository environment suffix; must match the consuming dev root."
  type        = string
  default     = "dev"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,11}$", var.environment))
    error_message = "Use a lowercase environment name of 1-12 characters."
  }
}
variable "tags" {
  description = "Additional ownership tags."
  type        = map(string)
  default     = {}
}
