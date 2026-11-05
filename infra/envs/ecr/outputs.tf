output "repository_name" {
  description = "Repository name for image commands and dev lookup."
  value       = module.ecr.repository_name
}
output "repository_url" {
  description = "Repository URL; keep account-specific output private."
  value       = module.ecr.repository_url
}
output "repository_arn" {
  description = "Repository ARN for scoped permissions."
  value       = module.ecr.repository_arn
}
