variable "name" {
  description = "Private ECR repository name."
  type        = string
}
variable "tags" {
  description = "Consistent project tags."
  type        = map(string)
  default     = {}
}
