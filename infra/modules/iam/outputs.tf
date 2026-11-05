output "execution_role_arn" {
  description = "ECS agent execution role ARN."
  value       = aws_iam_role.execution.arn
  depends_on  = [aws_iam_role_policy.execution]
}
output "task_role_arn" {
  description = "Unprivileged application task role ARN."
  value       = aws_iam_role.task.arn
}
