mock_provider "aws" {
  override_during = plan
  mock_resource "aws_s3_bucket" {
    defaults = { id = "rdp-test-state-only", arn = "arn:aws:s3:::rdp-test-state-only" }
  }
}
variables { state_bucket_name = "rdp-test-state-only" }
run "private_versioned_encrypted_state" {
  command = plan
  assert {
    condition     = aws_s3_bucket_public_access_block.state.block_public_acls && aws_s3_bucket_public_access_block.state.block_public_policy && aws_s3_bucket_public_access_block.state.ignore_public_acls && aws_s3_bucket_public_access_block.state.restrict_public_buckets
    error_message = "State bucket must block all public access."
  }
  assert {
    condition     = aws_s3_bucket_versioning.state.versioning_configuration[0].status == "Enabled" && one(aws_s3_bucket_server_side_encryption_configuration.state.rule).apply_server_side_encryption_by_default[0].sse_algorithm == "AES256" && !aws_s3_bucket.state.force_destroy
    error_message = "State must be encrypted, versioned and protected from force deletion."
  }
  assert {
    condition     = jsondecode(aws_s3_bucket_policy.https_only.policy).Statement[0].Effect == "Deny" && jsondecode(aws_s3_bucket_policy.https_only.policy).Statement[0].Condition.Bool["aws:SecureTransport"] == "false"
    error_message = "State bucket policy must deny insecure transport."
  }
}
