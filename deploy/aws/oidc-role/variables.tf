variable "aws_region" {
  description = "AWS region for AEGIS deployment."
  type        = string
  default     = "af-south-1"
}

variable "aws_account_id" {
  description = "12-digit AWS account ID."
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "aws_account_id must be a 12-digit AWS account ID."
  }
}

variable "github_repository" {
  description = "Exact GitHub repository allowed to assume the role."
  type        = string
  default     = "princezdavidz-ctrl/Aegis-"
}

variable "ecr_repository" {
  type    = string
  default = "aegis-api"
}

variable "ecs_cluster" {
  type    = string
  default = "aegis"
}

variable "ecs_service" {
  type    = string
  default = "aegis-api"
}

variable "frontend_bucket" {
  description = "Private S3 bucket receiving the built frontend."
  type        = string
}

variable "cloudfront_distribution_id" {
  description = "CloudFront distribution invalidated after frontend deployment."
  type        = string
}
