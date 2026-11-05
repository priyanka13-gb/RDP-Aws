# Standalone rule resources avoid dependency cycles between security groups.
resource "aws_security_group" "alb" {
  name_prefix = "${local.name}-alb-"
  description = "Public ALB: configured client port to ECS only"
  vpc_id      = aws_vpc.this.id
  tags        = merge(local.tags, { Name = "${local.name}-alb" })
}

resource "aws_security_group" "ecs" {
  name_prefix = "${local.name}-ecs-"
  description = "Future ECS tasks: ingress only from ALB"
  vpc_id      = aws_vpc.this.id
  tags        = merge(local.tags, { Name = "${local.name}-ecs" })
}

resource "aws_security_group" "postgresql" {
  name_prefix = "${local.name}-postgresql-"
  description = "Future PostgreSQL: ingress only from ECS tasks"
  vpc_id      = aws_vpc.this.id
  tags        = merge(local.tags, { Name = "${local.name}-postgresql" })
}

# Preserve the existing resource address while allowing the explicit HTTP demo port.
resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  for_each = var.alb_ingress_cidrs

  security_group_id = aws_security_group.alb.id
  description       = "ALB clients on port ${var.alb_ingress_port}"
  cidr_ipv4         = each.value
  ip_protocol       = "tcp"
  from_port         = var.alb_ingress_port
  to_port           = var.alb_ingress_port
  tags              = local.tags
}

resource "aws_vpc_security_group_egress_rule" "alb_to_ecs" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.ecs.id
  description                  = "ALB forwarding and health checks to FastAPI"
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  tags                         = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "ecs_from_alb" {
  security_group_id            = aws_security_group.ecs.id
  referenced_security_group_id = aws_security_group.alb.id
  description                  = "FastAPI only from the ALB"
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  tags                         = local.tags
}

resource "aws_vpc_security_group_egress_rule" "ecs_to_postgresql" {
  security_group_id            = aws_security_group.ecs.id
  referenced_security_group_id = aws_security_group.postgresql.id
  description                  = "ECS to PostgreSQL"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  tags                         = local.tags
}

resource "aws_vpc_security_group_ingress_rule" "postgresql_from_ecs" {
  security_group_id            = aws_security_group.postgresql.id
  referenced_security_group_id = aws_security_group.ecs.id
  description                  = "PostgreSQL only from ECS"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
  tags                         = local.tags
}

# Public demo task ENIs use the IGW; private tasks require NAT or VPC endpoints.
resource "aws_vpc_security_group_egress_rule" "ecs_https" {
  security_group_id = aws_security_group.ecs.id
  description       = "HTTPS for image pulls and AWS APIs via configured outbound path"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  tags              = local.tags
}

# Adopt only this new VPC's default SG and remove its default allow rules.
resource "aws_default_security_group" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${local.name}-default-deny" })
}
