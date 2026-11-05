output "log_group_name" {
  description = "ECS application log group name."
  value       = aws_cloudwatch_log_group.app.name
}
output "log_group_arn" {
  description = "ECS application log group ARN."
  value       = aws_cloudwatch_log_group.app.arn
}
