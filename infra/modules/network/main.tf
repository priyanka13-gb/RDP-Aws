locals {
  name = "${var.project_name}-${var.environment}"
  tags = merge(var.tags, {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    NetworkMode = var.network_mode
  })
  # Stable AZ keys keep resource addresses readable. Preserve AZ order to preserve CIDRs.
  subnets = {
    for index, az in var.availability_zones : az => {
      public_cidr  = cidrsubnet(var.vpc_cidr, 8, index)
      private_cidr = cidrsubnet(var.vpc_cidr, 8, index + 10)
    }
  }
  nat_azs = var.network_mode == "production_like" ? (
    var.nat_gateway_mode == "per_az" ? toset(var.availability_zones) : toset(slice(var.availability_zones, 0, 1))
  ) : toset([])
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = local.name })
}

resource "aws_subnet" "public" {
  for_each = local.subnets

  vpc_id                  = aws_vpc.this.id
  availability_zone       = each.key
  cidr_block              = each.value.public_cidr
  map_public_ip_on_launch = false
  tags                    = merge(local.tags, { Name = "${local.name}-public-${each.key}", Tier = "public" })
}

resource "aws_subnet" "private" {
  for_each = local.subnets

  vpc_id                  = aws_vpc.this.id
  availability_zone       = each.key
  cidr_block              = each.value.private_cidr
  map_public_ip_on_launch = false
  tags                    = merge(local.tags, { Name = "${local.name}-private-${each.key}", Tier = "private" })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${local.name}-igw" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${local.name}-public" })
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  for_each = local.subnets

  subnet_id      = aws_subnet.public[each.key].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table" "private" {
  for_each = local.subnets

  vpc_id = aws_vpc.this.id
  tags   = merge(local.tags, { Name = "${local.name}-private-${each.key}" })
}

resource "aws_route_table_association" "private" {
  for_each = local.subnets

  subnet_id      = aws_subnet.private[each.key].id
  route_table_id = aws_route_table.private[each.key].id
}
