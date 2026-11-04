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
