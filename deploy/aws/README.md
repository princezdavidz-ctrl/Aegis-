# AEGIS AWS deployment foundation

Target region: `af-south-1` (Cape Town). This repository contains deployment automation and the GitHub Actions OIDC role definition. It does **not** create AWS compute, database, storage or networking resources; those must be provisioned in your AWS account.

## Deployment shape

- API: Docker image in ECR, deployed to an existing ECS Fargate service behind an HTTPS load balancer.
- Web portal: built from `frontend/`, uploaded to an existing private S3 origin and served through CloudFront.
- Database: PostgreSQL with the checked-in AEGIS Alembic migrations. Use private networking, encryption, backups and PostgreSQL RLS. Do not point AEGIS at the unrelated ARA database.
- Secrets: AWS Secrets Manager values injected into the ECS task definition; never commit credentials.
- Desktop: Flutter desktop remains a client and connects to the HTTPS API.

The workflow deliberately deploys only on manual dispatch. It does not deploy production on every push.

## 1. Provision the baseline AWS services

Create (or have an AWS administrator create) these resources in `af-south-1`:

1. ECR repository named `aegis-api`.
2. ECS cluster and Fargate service named `aegis` / `aegis-api`, with an HTTPS ALB target group on container port 8000 and health path `/health/ready`.
3. Task execution role with ECR pull and CloudWatch Logs permissions; task role with only the runtime permissions AEGIS actually needs.
4. Private S3 bucket for the frontend, CloudFront distribution with Origin Access Control, HTTPS redirect and SPA fallback to `index.html`.
5. RDS PostgreSQL in private subnets, encrypted, backups enabled, not publicly accessible.
6. Secrets Manager entries for the database URL, OIDC settings and optional AI provider settings. Configure `AEGIS_OIDC_JWKS_CACHE_SECONDS` only when needed (default 300 seconds; allowed range 30–600). A shorter cache bounds how long a removed signing key may remain trusted. Keep AI disabled until a real provider is deliberately configured.

Do not use public database access. Restrict ALB ingress to HTTPS and ECS ingress to the ALB security group. Configure CloudWatch log retention and budget alerts.

## 2. Create or verify the GitHub OIDC provider and deployment role

The Terraform in `deploy/aws/oidc-role` **reads an existing** IAM OIDC provider using a Terraform data source. It does not create that provider. Before applying Terraform, an AWS administrator must verify that the provider exists:

- Provider URL: `https://token.actions.githubusercontent.com`
- Audience: `sts.amazonaws.com`

If it is missing, create it in IAM → Identity providers → Add provider → OpenID Connect, using the URL and audience above. Do not create a duplicate if it already exists.

Then run from `deploy/aws/oidc-role` after supplying the required Terraform variables:

```sh
terraform init
terraform plan
terraform apply
```

The role trust policy is restricted to `princezdavidz-ctrl/Aegis-` on `refs/heads/main`. The Terraform output `github_actions_role_arn` is the value for the GitHub repository variable `AWS_ROLE_ARN`.

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

## 4. Apply database migrations as a separate reviewed task

The API image contains the Alembic configuration and migration files. Run a one-off ECS task using the same image, private database connectivity and a dedicated migration-owner database credential:

```sh
alembic -c /app/alembic.ini upgrade head
```

Do not use the migration-owner credential as the API runtime credential. The runtime database role must be non-superuser, must not have `BYPASSRLS`, and must receive only the table privileges it needs. Verify tenant RLS with the PostgreSQL integration tests before enabling tenant data routes. Never use a superuser or table-owner connection as the normal API runtime role.

## 5. Configure PostgreSQL roles

Use the checked-in role separation scripts in `deploy/postgres/`:

1. Run `roles.sql` as the database administrator before migrations.
2. Set independent passwords for `aegis_migrator` and `aegis_runtime` using your approved secret-management process.
3. Apply Alembic migrations with the `aegis_migrator` connection.
4. Run `grants.sql` as `aegis_migrator` after migrations.
5. Configure the API task with the `aegis_runtime` connection only.

The runtime role has SELECT access for tenant/membership resolution and SELECT/INSERT for audit events. It cannot update/delete audit rows, create tenants or create memberships. Do not grant additional permissions until the corresponding APIs, RLS policies and integration tests exist. See [PostgreSQL role separation](../postgres/README.md).

## 6. Run deployment

Open **Actions → Deploy AEGIS to AWS → Run workflow** on `main`. The workflow builds and pushes the API image tagged with the commit SHA, updates the ECS task definition to that immutable image, builds the frontend, uploads it to S3 and invalidates CloudFront.

The workflow fails closed if required variables or AWS resources are missing. Review the run and ECS service health before directing users to the deployment.

## Operational cautions

- This is deployment automation, not proof of a production-ready service. A live IdP, database, secrets, tenant provisioning, migrations, backups, alerting and incident procedures remain necessary.
- The current readiness endpoint reports application readiness and explicitly says external dependencies are not configured; replace it with dependency-aware checks before using it as the only production readiness signal.
- Do not run database migrations automatically in the web deployment job. Use a separately reviewed one-off migration task with a controlled release window.
- The AI gateway remains disabled unless a provider and key are explicitly configured.
- Review AWS service availability and pricing in `af-south-1` before provisioning. ECS, ALB, RDS, NAT, S3 and CloudFront can incur charges.


## Separate tenant-provisioning database credential

The API uses two database connections. AEGIS_DATABASE_URL uses the restricted aegis_runtime role. AEGIS_PROVISIONER_DATABASE_URL uses the separate aegis_provisioner role, which has no direct table privileges and can execute only the audited tenant-provisioning function. Set independent credentials in Secrets Manager. Do not use the migration-owner credential in the API.
