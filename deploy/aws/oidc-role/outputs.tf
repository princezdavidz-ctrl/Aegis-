output "github_actions_role_arn" {
  description = "Set this as the GitHub repository Actions variable AWS_ROLE_ARN."
  value       = aws_iam_role.github_actions.arn
}

output "github_oidc_provider_arn" {
  value = data.aws_iam_openid_connect_provider.github.arn
}
