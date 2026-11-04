# No Elastic IPs, NAT gateways, or private default routes in cost_saver mode.
resource "aws_eip" "nat" {
  for_each = local.nat_azs

  domain = "vpc"
  tags   = merge(local.tags, { Name = "${local.name}-nat-${each.key}" })
}

resource "aws_nat_gateway" "this" {
  for_each = local.nat_azs

  allocation_id = aws_eip.nat[each.key].id
  subnet_id     = aws_subnet.public[each.key].id
  tags          = merge(local.tags, { Name = "${local.name}-nat-${each.key}" })
  depends_on    = [aws_internet_gateway.this]
}

resource "aws_route" "private_egress" {
  for_each = var.network_mode == "production_like" ? local.subnets : {}

  route_table_id         = aws_route_table.private[each.key].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.this[var.nat_gateway_mode == "per_az" ? each.key : var.availability_zones[0]].id
}
