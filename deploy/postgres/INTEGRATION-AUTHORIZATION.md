# Integration authorization registry

The registry records customer-approved connector requests without implementing provider authentication or data collection.

## API

- `GET /api/v1/integrations`: list integrations for the active tenant.
- `POST /api/v1/integrations`: tenant admins/security managers request an integration with explicit provider-specific read-only scopes.
- `POST /api/v1/integrations/{id}/approve`: tenant admins approve a subset of the requested scopes.
- `POST /api/v1/integrations/{id}/revoke`: tenant admins revoke the integration authorization record.

Supported providers: GitHub, AWS, Azure, GCP, Wazuh, Suricata, Trivy and Semgrep. Requested scopes are allowlisted per provider. Wildcards and write scopes are rejected. Approval moves the record to `approved_pending_verification`; no API route can mark it active. A future connector worker must complete provider authentication, verify granted scopes and record the verification result before activation.

No API key, access token, refresh token or client secret is accepted or stored. The schema rejects unknown credential fields. Secret-vault binding, OAuth callbacks, provider-side scope verification, connector runtime and telemetry synchronization are separate later tasks.

Integration records are tenant-scoped by RLS. The provisioner database role receives EXECUTE on controlled functions only; all request, approval and revocation actions append immutable audit events.
