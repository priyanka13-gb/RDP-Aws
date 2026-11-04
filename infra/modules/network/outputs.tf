output "vpc_id" {
  description = "VPC ID."
  value       = aws_vpc.this.id
}

output "vpc_cidr" {
  description = "VPC IPv4 CIDR."
  value       = aws_vpc.this.cidr_block
}

output "public_subnet_ids" {
  description = "Public subnet IDs in availability_zones input order."
  value       = [for az in var.availability_zones : aws_subnet.public[az].id]
}

output "private_subnet_ids" {
  description = "Private subnet IDs in availability_zones input order."
  value       = [for az in var.availability_zones : aws_subnet.private[az].id]
}

output "private_route_table_ids" {
  description = "Private route table IDs keyed by AZ; useful for future VPC endpoints."
  value       = { for az, table in aws_route_table.private : az => table.id }
}

output "security_group_ids" {
  description = "Security groups to attach to future ALB, ECS tasks, and PostgreSQL."
  value = {
    alb        = aws_security_group.alb.id
    ecs        = aws_security_group.ecs.id
    postgresql = aws_security_group.postgresql.id
  }
}

output "nat_gateway_ids" {
  description = "NAT IDs keyed by AZ; empty in cost_saver mode."
  value       = { for az, nat in aws_nat_gateway.this : az => nat.id }
}
