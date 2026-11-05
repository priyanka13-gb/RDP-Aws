output "dns_name" {
  description = "Demo ALB DNS name; HTTP only."
  value       = aws_lb.this.dns_name
}
output "target_group_arn" {
  description = "IP target group; listener exists before ECS consumes this output."
  value       = aws_lb_target_group.app.arn
  depends_on  = [aws_lb_listener.http]
}
