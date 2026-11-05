output "state_bucket_name" {
  description = "Use this bucket name in the dev backend configuration."
  value       = aws_s3_bucket.state.id
}

output "state_bucket_arn" {
  description = "State bucket ARN for scoped operator access."
  value       = aws_s3_bucket.state.arn
}
