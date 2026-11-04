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
  description = "Two Mumbai AZ names; confirm account availability before any future deployment."
  type        = list(string)
  default     = ["ap-south-1a", "ap-south-1b"]

  validation {
    condition     = alltrue([for az in var.availability_zones : can(regex("^ap-south-1[a-z]$", az))])
    error_message = "Dev AZ names must belong to ap-south-1."
  }
}

variable "alb_ingress_cidrs" {
  description = "Future HTTPS ALB client ranges; narrow to your trusted ranges if appropriate."
  type        = set(string)
  default     = ["0.0.0.0/0"]
}

variable "tags" {
  description = "Optional additional ownership or cost allocation tags."
  type        = map(string)
  default     = {}
}
