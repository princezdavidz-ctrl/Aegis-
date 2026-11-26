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
