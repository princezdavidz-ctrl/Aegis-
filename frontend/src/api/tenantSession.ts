/**
 * Ephemeral identity context supplied by a future trusted browser OIDC adapter.
 * Tokens must never be persisted in local storage or Vite environment variables.
 */
export interface TenantSession {
  readonly accessToken: string;
  /** Tenant slug is only a selector; the API resolves membership and tenant ID. */
  readonly tenantSlug: string;
}
