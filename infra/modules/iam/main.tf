data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
data "aws_region" "current" {}

locals {
  trust_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow", Action = "sts:AssumeRole"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
        ArnLike      = { "aws:SourceArn" = "arn:${data.aws_partition.current.partition}:ecs:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:*" }
      }
    }]
  })
}

resource "aws_iam_role" "execution" {
  name               = "${var.name}-execution"
  assume_role_policy = local.trust_policy
  tags               = var.tags
}

resource "aws_iam_role" "task" {
  name               = "${var.name}-task"
  assume_role_policy = local.trust_policy
  tags               = var.tags
  # The current FastAPI app calls no AWS APIs: intentionally no permission policies.
}

resource "aws_iam_role_policy" "execution" {
  name = "${var.name}-execution"
  role = aws_iam_role.execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat([
      {
        Sid = "ECRToken", Effect = "Allow"
        # GetAuthorizationToken does not support repository-level resource scoping.
        Action = ["ecr:GetAuthorizationToken"], Resource = ["*"]
      },
      {
        Sid      = "PullApplicationImage", Effect = "Allow"
        Action   = ["ecr:BatchCheckLayerAvailability", "ecr:GetDownloadUrlForLayer", "ecr:BatchGetImage"]
        Resource = [var.repository_arn]
      },
      {
        Sid      = "WriteApplicationLogs", Effect = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = ["${trimsuffix(var.log_group_arn, ":*")}:log-stream:*"]
      }
      ], length(var.ssm_parameter_arns) > 0 ? [{
        Sid    = "ReadAllowedParameters", Effect = "Allow"
        Action = ["ssm:GetParameters"], Resource = sort(tolist(var.ssm_parameter_arns))
        }] : [], length(var.ssm_parameter_arns) > 0 && length(var.ssm_kms_key_arns) > 0 ? [{
        Sid    = "DecryptParameterKeys", Effect = "Allow"
        Action = ["kms:Decrypt"], Resource = sort(tolist(var.ssm_kms_key_arns))
        Condition = {
          StringEquals = { "kms:ViaService" = "ssm.${data.aws_region.current.region}.${data.aws_partition.current.dns_suffix}" }
          ArnEquals    = { "kms:EncryptionContext:PARAMETER_ARN" = sort(tolist(var.ssm_parameter_arns)) }
        }
      }] : []
    )
  })
}
