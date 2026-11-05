output "repository_url" {
  description = "Repository URL, without an image tag."
  value       = aws_ecr_repository.this.repository_url
}
output "repository_arn" {
  description = "Repository ARN for scoped image-pull permissions."
  value       = aws_ecr_repository.this.arn
}

output "repository_name" {
  description = "Managed ECR repository name."
  value       = aws_ecr_repository.this.name
}
