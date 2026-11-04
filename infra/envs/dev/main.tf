module "network" {
  source = "../../modules/network"

  project_name       = "aws-resilient-delivery-platform"
  environment        = "dev"
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = var.availability_zones
  network_mode       = var.network_mode
  nat_gateway_mode   = var.nat_gateway_mode
  alb_ingress_cidrs  = var.alb_ingress_cidrs
  tags               = var.tags
}
