# AWS deployment

See [deploy/aws/README.md](../deploy/aws/README.md) for provisioning prerequisites, GitHub OIDC setup, repository variables and release steps.

The API container is built from the repository root with `backend/Dockerfile`; this is required because the image installs the shared `services/ai` package. The GitHub Actions release workflow is manual-only and uses short-lived AWS credentials via OIDC. No long-lived AWS keys are stored in GitHub.

Default target region: `af-south-1`. Infrastructure provisioning and production release require an authorized AWS account administrator.
