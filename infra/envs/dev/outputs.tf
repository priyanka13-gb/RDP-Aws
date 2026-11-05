output "availability_zones" {
  description = "Selected AZs in CIDR assignment order; pin this order before future changes to deployed infrastructure."
  value       = local.availability_zones
}

output "vpc_id" {
  description = "Development VPC ID."
  value       = module.network.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs ordered by AZ."
  value       = module.network.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnet IDs ordered by AZ."
  value       = module.network.private_subnet_ids
}

output "security_group_ids" {
  description = "Future ALB, ECS, and PostgreSQL security group IDs."
  value       = module.network.security_group_ids
}

output "nat_gateway_ids" {
  description = "Empty by default; NAT gateway IDs when explicitly enabled."
  value       = module.network.nat_gateway_ids
}

output "ecr_repository_url" {
  description = "ECR repository for a future approved image push."
  value       = data.aws_ecr_repository.app.repository_url
}
output "alb_dns_name" {
  description = "Temporary HTTP demo ALB DNS name."
  value       = module.alb.dns_name
}
output "application_url" {
  description = "HTTP demo only: no credentials or real user data."
  value       = "http://${module.alb.dns_name}"
}
output "ecs_cluster_name" {
  description = "Application ECS cluster."
  value       = module.ecs_service.cluster_name
}
output "ecs_service_name" {
  description = "Application ECS service."
  value       = module.ecs_service.service_name
}
output "log_group_name" {
  description = "Application log group with seven-day retention."
  value       = module.observability.log_group_name
}
