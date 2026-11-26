# KMS-backed webhook secret envelope

The provider implements envelope encryption for endpoint webhook signing
secrets. AWS KMS GenerateDataKey(AES_256) creates a per-operation data key.
AES-256-GCM encrypts the signing secret in process; only the KMS-wrapped data
key and authenticated ciphertext are persisted.

## Security properties

- KMS key material never leaves KMS. The plaintext data key exists only in
  process memory during an operation.
- The versioned envelope contains a random 96-bit GCM nonce, wrapped data key
  and authenticated ciphertext/tag.
- KMS EncryptionContext and AES-GCM additional authenticated data bind every
  operation to the AEGIS purpose, tenant ID, destination ID and secret version.
  Copying ciphertext across tenants, destinations or versions fails closed.
- Inject a boto3 KMS client created with the ECS task role; do not configure
  static AWS credentials.
- Persist envelope bytes in secret_ciphertext, the configured KMS key ARN in
  secret_key_ref, format version 1, and increment secret_version atomically
  during rotation.
- Never log plaintext secrets, data keys, envelopes or provider request data.

## Not yet enabled

This is an encryption primitive, not a destination API or delivery worker.
Keep delivery disabled until tenant-scoped CRUD, audit, rotation/revocation,
least-privilege KMS IAM policy, pinned-IP TLS delivery, quotas, kill switch and
integration tests are complete. Scope the KMS key policy to the AEGIS task role
and only the required GenerateDataKey and Decrypt actions.
