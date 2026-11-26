# Webhook destination management database boundary

Migration 0014 adds three SECURITY DEFINER operations for creating, listing
and disabling webhook destinations. Each function has a fixed search_path,
checks active tenant membership and manager role from the database, and is
owned by aegis_migrator. Only aegis_provisioner receives EXECUTE; the role
receives no direct table privileges.

The create operation accepts only an encrypted secret envelope and KMS key
reference. It does not accept plaintext secret material. List results omit
ciphertext and key references. Disable is tenant- and destination-scoped.

The API layer must still authenticate the caller, validate the HTTPS URL with
validate_webhook_url, obtain ciphertext from the configured KMS envelope
provider, enforce tenant role, rate limits and audit requirements, and never
return ciphertext. Delivery remains disabled. Rotation and deletion/revocation
are separate follow-up work; this migration does not grant worker access.


## API and KMS runtime

The FastAPI application exposes manager-only endpoints:

- `POST /api/v1/webhook-destinations` creates a destination.
- `GET /api/v1/webhook-destinations` lists destination metadata.
- `DELETE /api/v1/webhook-destinations/{destination_id}` disables a destination.

Set `AEGIS_WEBHOOK_KMS_KEY_ID` to the customer-managed or platform-managed
AWS KMS key ARN/ID. Optionally set `AEGIS_WEBHOOK_KMS_REGION`; otherwise boto3
uses the AWS runtime's configured region. boto3 uses the default AWS credential
provider chain (ECS task role, EC2 instance profile, or workload identity).
Do not configure static AWS access keys in AEGIS environment variables.

The API generates a cryptographically random 256-bit signing secret, encrypts
it with the KMS envelope provider, and stores only the envelope and key
reference. The raw signing secret is returned once in URL-safe base64 without
padding in the create response. Capture it securely at creation time; it is
not available from subsequent list calls. The KMS encryption context binds
purpose, tenant ID, destination ID and secret version. Migration 0015 provides
the create function that accepts the preselected destination UUID required for
that binding.

If KMS is not configured, create requests fail closed with HTTP 503. Listing
and disabling do not require decrypting a secret. This API does not activate
delivery; the outbox worker, secret rotation, audit events, and delivery
outcome reporting remain separate release gates.
