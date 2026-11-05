# This exercises the real dev module graph with synthetic AWS responses only.
mock_provider "aws" {
  override_during = plan
  mock_data "aws_availability_zones" {
    defaults = { names = ["ap-southeast-2c", "ap-southeast-2a", "ap-southeast-2b"] }
  }
  mock_data "aws_caller_identity" { defaults = { account_id = "123456789012" } }
  mock_data "aws_partition" { defaults = { partition = "aws", dns_suffix = "amazonaws.com" } }
  mock_data "aws_region" { defaults = { region = "ap-southeast-2" } }
  mock_data "aws_ecr_repository" {
    defaults = {
      repository_url = "123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/aws-resilient-delivery-platform-dev"
      arn            = "arn:aws:ecr:ap-southeast-2:123456789012:repository/aws-resilient-delivery-platform-dev"
    }
  }
  mock_resource "aws_cloudwatch_log_group" {
    defaults = { arn = "arn:aws:logs:ap-southeast-2:123456789012:log-group:/ecs/aws-resilient-delivery-platform-dev" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/mock-role" }
  }
  mock_resource "aws_lb" {
    defaults = {
      arn      = "arn:aws:elasticloadbalancing:ap-southeast-2:123456789012:loadbalancer/app/test/1234567890123456"
      dns_name = "test-demo.elb.amazonaws.com"
    }
  }
  mock_resource "aws_lb_target_group" {
    defaults = { arn = "arn:aws:elasticloadbalancing:ap-southeast-2:123456789012:targetgroup/test/1234567890123456" }
  }
  mock_resource "aws_ecs_cluster" {
    defaults = { id = "arn:aws:ecs:ap-southeast-2:123456789012:cluster/test" }
  }
  mock_resource "aws_ecs_task_definition" {
    defaults = { arn = "arn:aws:ecs:ap-southeast-2:123456789012:task-definition/test:1" }
  }
}
variables {
  container_image = "123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/aws-resilient-delivery-platform-dev:test-release"
}
run "dev_modules_integrate" {
  command = plan
  assert {
    condition     = var.aws_region == "ap-southeast-2" && output.availability_zones == tolist(["ap-southeast-2a", "ap-southeast-2b"])
    error_message = "Sydney defaults must dynamically choose the first two sorted discovered AZs."
  }
  assert {
    condition     = length(output.nat_gateway_ids) == 0 && output.application_url == "http://test-demo.elb.amazonaws.com" && output.ecs_service_name == "aws-resilient-delivery-platform-dev" && output.log_group_name == "/ecs/aws-resilient-delivery-platform-dev"
    error_message = "Dev outputs must wire the app modules together with no NAT."
  }
}

run "pinned_az_order_is_preserved" {
  command = plan
  variables { availability_zones = ["ap-southeast-2c", "ap-southeast-2a"] }
  assert {
    condition     = output.availability_zones == tolist(["ap-southeast-2c", "ap-southeast-2a"])
    error_message = "Explicit AZ order must be preserved for stable CIDR allocation."
  }
}
run "rds_is_not_enabled" {
  command = plan
  variables { enable_rds = true }
  expect_failures = [var.enable_rds]
}
run "ssm_requires_opt_in" {
  command = plan
  variables {
    ssm_parameters = { DEMO_SETTING = "arn:aws:ssm:ap-southeast-2:123456789012:parameter/test/demo" }
  }
  expect_failures = [var.ssm_parameters]
}
