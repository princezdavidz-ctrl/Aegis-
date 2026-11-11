export interface TenantSession {
  /** Short-lived access token supplied by a trusted OIDC session adapter. */
  accessToken: string;
  /** Tenant slug selected by the user; membership is resolved by the API. */
  tenantSlug: string;
}

export interface TenantProfile {
  id: string;
  slug: string;
  display_name: string;
  industry: string | null;
  organization_size: string | null;
  region: string | null;
  data_retention_days: number;
  policy_profile: 'baseline' | 'strict' | 'regulated';
  created_at: string;
}

type FetchImplementation = typeof fetch;

export class TenantProfileApiError extends Error {
  readonly status: number;
  readonly code: 'request_failed' | 'invalid_response';

  constructor(status: number, code: 'request_failed' | 'invalid_response' = 'request_failed') {
    super(code === 'invalid_response' ? 'The organization service returned an invalid response.' : 'The organization request failed.');
    this.name = 'TenantProfileApiError';
    this.status = status;
    this.code = code;
  }
}

const TENANT_SLUG_PATTERN = /^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function normalizeBaseUrl(value: string): string {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new TypeError('A valid AEGIS API base URL is required.');
  }

  const isLoopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  const secureTransport = url.protocol === 'https:' || (url.protocol === 'http:' && isLoopback);

  if (
    !secureTransport ||
    url.username.length > 0 ||
    url.password.length > 0 ||
    url.search.length > 0 ||
    url.hash.length > 0 ||
    (url.pathname !== '' && url.pathname !== '/')
  ) {
    throw new TypeError('The AEGIS API base URL must be an HTTPS origin (HTTP is allowed only for loopback development).');
  }

  return url.origin;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string';
}

function isTenantProfile(value: unknown): value is TenantProfile {
  if (!isRecord(value)) return false;

  const allowedKeys = new Set([
    'id',
    'slug',
    'display_name',
    'industry',
    'organization_size',
    'region',
    'data_retention_days',
    'policy_profile',
    'created_at',
  ]);
  if (Object.keys(value).some((key) => !allowedKeys.has(key))) return false;

  return (
    typeof value.id === 'string' &&
    UUID_PATTERN.test(value.id) &&
    typeof value.slug === 'string' &&
    TENANT_SLUG_PATTERN.test(value.slug) &&
    typeof value.display_name === 'string' &&
    value.display_name.trim().length > 0 &&
    isNullableString(value.industry) &&
    isNullableString(value.organization_size) &&
    isNullableString(value.region) &&
    Number.isInteger(value.data_retention_days) &&
    Number(value.data_retention_days) >= 30 &&
    Number(value.data_retention_days) <= 3650 &&
    ['baseline', 'strict', 'regulated'].includes(String(value.policy_profile)) &&
    typeof value.created_at === 'string' &&
    Number.isFinite(Date.parse(value.created_at))
  );
}

export function createTenantProfileClient(
  baseUrl: string,
  fetchImplementation: FetchImplementation = fetch,
) {
  const apiBaseUrl = normalizeBaseUrl(baseUrl);

  return Object.freeze({
    async getProfile(session: TenantSession): Promise<TenantProfile> {
      const accessToken = session.accessToken.trim();
      const tenantSlug = session.tenantSlug.trim();

      if (accessToken.length === 0 || accessToken.length > 8192) {
        throw new TypeError('A valid short-lived access token is required.');
      }
      if (!TENANT_SLUG_PATTERN.test(tenantSlug)) {
        throw new TypeError('A valid tenant slug is required.');
      }

      const response = await fetchImplementation(`${apiBaseUrl}/api/v1/tenants/profile`, {
        method: 'GET',
        headers: {
          Accept: 'application/json',
          Authorization: `Bearer ${accessToken}`,
          'X-AEGIS-Tenant': tenantSlug,
        },
        cache: 'no-store',
        credentials: 'omit',
        redirect: 'error',
        referrerPolicy: 'no-referrer',
      });

      if (!response.ok) {
        throw new TenantProfileApiError(response.status);
      }

      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        throw new TenantProfileApiError(response.status, 'invalid_response');
      }

      if (!isTenantProfile(payload)) {
        throw new TenantProfileApiError(response.status, 'invalid_response');
      }

      return payload;
    },
  });
}
