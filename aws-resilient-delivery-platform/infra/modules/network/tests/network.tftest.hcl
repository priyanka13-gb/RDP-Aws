# Mock provider + plan commands only: no AWS calls and no resource creation.
mock_provider "aws" {}

variables {
  availability_zones = ["ap-south-1a", "ap-south-1b"]
}

run "cost_saver_has_no_nat" {
  command = plan

  assert {
    condition     = length(aws_nat_gateway.this) == 0 && length(aws_eip.nat) == 0 && length(aws_route.private_egress) == 0
    error_message = "Default mode must have no NAT, EIPs, or private internet routes."
  }
  assert {
    condition     = length(aws_subnet.public) == 2 && length(aws_subnet.private) == 2 && length(aws_route_table.private) == 2
    error_message = "Exactly two public/private subnets and private route tables are required."
  }
  assert {
    condition     = aws_subnet.public["ap-south-1a"].cidr_block == "10.0.0.0/24" && aws_subnet.private["ap-south-1b"].cidr_block == "10.0.11.0/24"
    error_message = "Subnet CIDR allocation changed unexpectedly."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.ecs_from_alb.from_port == 8000 && aws_vpc_security_group_ingress_rule.ecs_from_alb.cidr_ipv4 == null && aws_vpc_security_group_ingress_rule.postgresql_from_ecs.from_port == 5432 && aws_vpc_security_group_ingress_rule.postgresql_from_ecs.cidr_ipv4 == null
    error_message = "ECS/PostgreSQL ingress must use SG references rather than IP ranges."
  }
}

run "per_az_nat" {
  command = plan
  variables {
    network_mode     = "production_like"
    nat_gateway_mode = "per_az"
  }
  assert {
    condition     = length(aws_nat_gateway.this) == 2 && length(aws_eip.nat) == 2 && length(aws_route.private_egress) == 2
    error_message = "Per-AZ mode requires two NATs, EIPs, and private routes."
  }
}

run "single_nat" {
  command = plan
  variables {
    network_mode     = "production_like"
    nat_gateway_mode = "single"
  }
  assert {
    condition     = length(aws_nat_gateway.this) == 1 && contains(keys(aws_nat_gateway.this), "ap-south-1a") && length(aws_route.private_egress) == 2
    error_message = "Single NAT must be in the first AZ and serve both private routes."
  }
}

run "reject_nat_in_cost_saver" {
  command = plan
  variables {
    nat_gateway_mode = "single"
  }
  expect_failures = [var.nat_gateway_mode]
}

run "require_explicit_production_nat" {
  command = plan
  variables {
    network_mode = "production_like"
  }
  expect_failures = [var.nat_gateway_mode]
}
