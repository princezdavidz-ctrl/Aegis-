# AEGIS AWS deployment foundation

Target region: `af-south-1` (Cape Town). This repository contains deployment automation and the GitHub Actions OIDC role definition. It does **not** create AWS resources until you apply the Terraform configuration in your AWS account.

## Deployment shape

- API: Docker image in ECR, deployed to an existing ECS Fargate service behind an HTTPS load balancer.
- Web portal: built from `frontend/`, uploaded to an existing private S3 origin and served through CloudFront.
- Database: PostgreSQL with the existing AEGIS Alembic migrations. Use private networking, encryption, backups and PostgreSQL RLS. Do not point AEGIS at the unrelated ARA database.
- Secrets: AWS Secrets Manager values injected into ECS task definition; never commit credentials.
- Desktop: Flutter desktop remains a client and connects to the HTTPS API.

The workflow deliberately deploys only on manual dispatch. It does not deploy production on every push.

## 1. Provision the baseline AWS services

Create (or have an AWS administrator create) these resources in `af-south-1`:

1. ECR repository named `aegis-api`.
2. ECS cluster and Fargate service named `aegis` / `aegis-api`, with an HTTPS ALB target group on container port 8000 and health path `/health/ready`.
3. Task execution role with ECR pull and CloudWatch Logs permissions; task role with only the runtime permissions AEGIS actually needs.
4. Private S3 bucket for the frontend, CloudFront distribution with Origin Access Control, HTTPS redirect and SPA fallback to `index.html`.
5. RDS PostgreSQL in private subnets, encrypted, backups enabled, not publicly accessible. Apply the checked-in Alembic migrations before enabling protected routes.
6. Secrets Manager entries for database URL, OIDC settings and AI provider settings. Keep AI disabled until a real provider is deliberately configured.

Do not use public database access. Restrict ALB ingress to HTTPS and ECS ingress to the ALB security group. Configure CloudWatch log retention and budget alerts.

## 2. Create the GitHub OIDC deployment role

The Terraform in `deploy/aws/oidc-role` creates the GitHub OIDC provider (if not already present) and a role scoped to this repository and the named deployment resources.

Run from that directory after setting the required variables:

```sh
terraform init
terraform plan
terraform apply
```

If your AWS account already has the GitHub OIDC provider `token.actions.githubusercontent.com`, import it into Terraform or adapt the configuration rather than creating a duplicate.

The Terraform output `github_actions_role_arn` is the value for the GitHub repository variable `AWS_ROLE_ARN`.

## 3. Configure GitHub repository variables

Set these under **Settings → Secrets and variables → Actions → Variables**:

- `AWS_ROLE_ARN`: Terraform output role ARN
- `AWS_REGION`: `af-south-1`
- `AWS_ACCOUNT_ID`: 12-digit AWS account ID
- `ECR_REPOSITORY`: `aegis-api`
- `ECS_CLUSTER`: `aegis`
- `ECS_SERVICE`: `aegis-api`
- `ECS_CONTAINER_NAME`: `aegis-api`
- `FRONTEND_S3_BUCKET`: private frontend bucket name
- `CLOUDFRONT_DISTRIBUTION_ID`: distribution ID

No AWS access key or secret access key is needed. GitHub Actions requests short-lived credentials through OIDC.

## 4. Run deployment

Open **Actions → Deploy AEGIS to AWS → Run workflow** on `main`. The workflow builds and pushes the API image tagged with the commit SHA, updates the ECS task definition to that immutable image, builds the frontend, uploads it to S3 and invalidates CloudFront.

The workflow will fail closed if required variables or AWS resources are missing. Review the run and the ECS service health before directing users to the deployment.

## Operational cautions

- This is deployment automation, not proof of a production-ready service. A live IdP, database, secrets, tenant provisioning, migrations, backups, alerting and incident procedures remain necessary.
- The current readiness endpoint reports application readiness and explicitly says external dependencies are not configured; replace it with dependency-aware checks before using it as the only production readiness signal.
- Do not run database migrations automatically in the web deployment job. Use a separately reviewed one-off migration task with a controlled release window.
- The AI gateway remains disabled unless a provider and key are explicitly configured.
- Review AWS service availability and pricing in `af-south-1` before provisioning. ECS, ALB, RDS, NAT, S3 and CloudFront can incur charges.
