variable "name" {
  description = "Application resource name."
  type        = string
}
variable "tags" {
  description = "Consistent project tags."
  type        = map(string)
  default     = {}
}
