variable "name" {
  description = "Application name; AWS LB names are deterministically shortened."
  type        = string
}
variable "vpc_id" {
  description = "VPC containing targets."
  type        = string
}
variable "public_subnet_ids" {
  description = "Public subnets across two AZs."
  type        = list(string)
}
variable "security_group_id" {
  description = "ALB SG with HTTP ingress and ECS-only port 8000 egress."
  type        = string
}
variable "tags" {
  description = "Consistent project tags."
  type        = map(string)
  default     = {}
}
