output "cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.this.name
}
output "service_name" {
  description = "ECS service name."
  value       = aws_ecs_service.app.name
}
output "task_definition_arn" {
  description = "Active task definition revision ARN."
  value       = aws_ecs_task_definition.app.arn
}
