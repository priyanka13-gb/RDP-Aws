variable "aws_region" {
  description = "Region for the state bucket."
  type        = string
  default     = "ap-southeast-2"
}

variable "state_bucket_name" {
  description = "Globally unique S3 bucket name selected by the operator; no credentials."
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$", var.state_bucket_name))
    error_message = "Choose a 3-63 character lowercase bucket name using letters, digits and hyphens."
  }
}

variable "tags" {
  description = "Additional state infrastructure tags."
  type        = map(string)
  default     = {}
}
