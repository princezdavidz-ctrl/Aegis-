provider "aws" {
  region = var.aws_region
}

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repository}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "aegis-github-actions-deploy"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
  description        = "Short-lived GitHub Actions deployment role for AEGIS main branch."
}

data "aws_iam_policy_document" "deploy" {
  statement {
    sid       = "EcrAuth"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "EcrPush"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability", "ecr:CompleteLayerUpload",
      "ecr:InitiateLayerUpload", "ecr:PutImage", "ecr:UploadLayerPart",
      "ecr:BatchGetImage", "ecr:DescribeImages"
    ]
    resources = ["arn:aws:ecr:${var.aws_region}:${var.aws_account_id}:repository/${var.ecr_repository}"]
  }

  statement {
    sid    = "EcsRelease"
    effect = "Allow"
    actions = ["ecs:DescribeClusters", "ecs:DescribeServices", "ecs:UpdateService"]
    resources = [
      "arn:aws:ecs:${var.aws_region}:${var.aws_account_id}:cluster/${var.ecs_cluster}",
      "arn:aws:ecs:${var.aws_region}:${var.aws_account_id}:service/${var.ecs_cluster}/${var.ecs_service}"
    ]
  }

  statement {
    sid       = "TaskDefinitionReadAndRegister"
    effect    = "Allow"
    actions   = ["ecs:DescribeTaskDefinition", "ecs:RegisterTaskDefinition"]
    resources = ["*"]
  }

  statement {
    sid       = "PassEcsTaskRoles"
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = [
      "arn:aws:iam::${var.aws_account_id}:role/aegis-ecs-task-execution",
      "arn:aws:iam::${var.aws_account_id}:role/aegis-ecs-task"
    ]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }

  statement {
    sid       = "FrontendBucketList"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.frontend_bucket}"]
  }

  statement {
    sid       = "FrontendObjects"
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload"]
    resources = ["arn:aws:s3:::${var.frontend_bucket}/*"]
  }

  statement {
    sid       = "CloudFrontInvalidation"
    effect    = "Allow"
    actions   = ["cloudfront:CreateInvalidation"]
    resources = ["arn:aws:cloudfront::${var.aws_account_id}:distribution/${var.cloudfront_distribution_id}"]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "aegis-github-actions-deploy"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.deploy.json
}
