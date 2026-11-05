mock_provider "aws" { override_during = plan }
run "isolated_repository" {
  command = plan
  assert {
    condition     = output.repository_name == "aws-resilient-delivery-platform-dev"
    error_message = "Repository name must match the dev lookup."
  }
}
