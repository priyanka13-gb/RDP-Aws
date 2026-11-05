variable "project_name" {
  description = "Project name used in resource names and tags."
  type        = string
  default     = "aws-resilient-delivery-platform"
}

variable "environment" {
  description = "Environment identifier used in resource names and tags."
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "Canonical IPv4 /16; public /24s use indexes 0,1 and private /24s 10,11."
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr)) && can(regex("/16$", var.vpc_cidr)) && try("${cidrhost(var.vpc_cidr, 0)}/16" == var.vpc_cidr, false)
    error_message = "vpc_cidr must be a canonical IPv4 /16, for example 10.0.0.0/16."
  }
}

variable "availability_zones" {
  description = "Exactly two distinct AZ names in the configured provider region, in stable order."
  type        = list(string)

  validation {
    condition     = length(var.availability_zones) == 2 && length(distinct(var.availability_zones)) == 2
    error_message = "Provide exactly two distinct availability zones."
  }
}

variable "network_mode" {
  description = "cost_saver prohibits NAT; production_like requires an explicit NAT topology."
  type        = string
  default     = "cost_saver"

  validation {
    condition     = contains(["cost_saver", "production_like"], var.network_mode)
    error_message = "network_mode must be cost_saver or production_like."
  }
}

variable "nat_gateway_mode" {
  description = "none for cost_saver; explicitly select single or per_az for production_like (billable)."
  type        = string
  default     = "none"

  validation {
    condition     = var.network_mode == "cost_saver" ? var.nat_gateway_mode == "none" : contains(["single", "per_az"], var.nat_gateway_mode)
    error_message = "cost_saver requires nat_gateway_mode=none; production_like requires an explicit single or per_az choice."
  }
}

variable "alb_ingress_cidrs" {
  description = "IPv4 client ranges allowed to reach the future ALB on HTTPS 443."
  type        = set(string)
  default     = ["0.0.0.0/0"]

  validation {
    condition     = length(var.alb_ingress_cidrs) > 0 && alltrue([for cidr in var.alb_ingress_cidrs : can(cidrnetmask(cidr))])
    error_message = "Provide one or more valid IPv4 CIDRs."
  }
}

variable "alb_ingress_port" {
  description = "ALB client port: 443 by default; 80 only for the temporary HTTP demo."
  type        = number
  default     = 443
  validation {
    condition     = contains([80, 443], var.alb_ingress_port)
    error_message = "ALB client port must be 80 or 443."
  }
}

variable "tags" {
  description = "Additional tags. Module-owned Project, Environment, ManagedBy and NetworkMode take precedence."
  type        = map(string)
  default     = {}
}
