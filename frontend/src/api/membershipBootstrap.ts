export const TENANT_MEMBERSHIP_ROLES = [
  'tenant_admin',
  'security_manager',
  'analyst',
  'viewer',
] as const;

export type TenantMembershipRole = (typeof TENANT_MEMBERSHIP_ROLES)[number];

export interface ActiveTenantMembership {
  tenant_slug: string;
  display_name: string;
  role: TenantMembershipRole;
}

export interface MembershipBootstrapResponse {
  memberships: ActiveTenantMembership[];
}

type FetchImplementation = typeof fetch;

export class MembershipBootstrapApiError extends Error {
  readonly status: number;
  readonly code: 'request_failed' | 'invalid_response';

  constructor(status: number, code: 'request_failed' | 'invalid_response' = 'request_failed') {
    super(code === 'invalid_response'
      ? 'The organization access service returned an invalid response.'
      : 'Organization access could not be loaded.');
    this.name = 'MembershipBootstrapApiError';
    this.status = status;
    this.code = code;
  }
}

const TENANT_SLUG_PATTERN = /^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$/;
const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f]/;
const MAX_MEMBERSHIPS = 100;

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

function isMembershipRole(value: unknown): value is TenantMembershipRole {
  return typeof value === 'string' &&
    (TENANT_MEMBERSHIP_ROLES as readonly string[]).includes(value);
}

function isActiveTenantMembership(value: unknown): value is ActiveTenantMembership {
  if (!isRecord(value)) return false;
  const allowedKeys = new Set(['tenant_slug', 'display_name', 'role']);
  if (Object.keys(value).some((key) => !allowedKeys.has(key))) return false;

  return (
    typeof value.tenant_slug === 'string' &&
    TENANT_SLUG_PATTERN.test(value.tenant_slug) &&
    typeof value.display_name === 'string' &&
    value.display_name.trim().length > 0 &&
    value.display_name.length <= 160 &&
    !CONTROL_CHARACTERS.test(value.display_name) &&
    isMembershipRole(value.role)
  );
}

function isMembershipBootstrapResponse(value: unknown): value is MembershipBootstrapResponse {
  if (!isRecord(value) || Object.keys(value).some((key) => key !== 'memberships')) return false;
  if (!Array.isArray(value.memberships) || value.memberships.length > MAX_MEMBERSHIPS) return false;
  if (!value.memberships.every(isActiveTenantMembership)) return false;

  const slugs = value.memberships.map((membership) => membership.tenant_slug);
  return new Set(slugs).size === slugs.length;
}

export function createMembershipBootstrapClient(
  baseUrl: string,
  fetchImplementation: FetchImplementation = fetch,
) {
  const apiBaseUrl = normalizeBaseUrl(baseUrl);

  return Object.freeze({
    async listMyMemberships(accessTokenValue: string): Promise<ActiveTenantMembership[]> {
      if (typeof accessTokenValue !== 'string') {
        throw new TypeError('A short-lived verified access token is required.');
      }
      const accessToken = accessTokenValue.trim();
      if (!accessToken || accessToken.length > 8192 || /[\u0000-\u001f\u007f]/.test(accessToken)) {
        throw new TypeError('A short-lived verified access token is required.');
      }

      const response = await fetchImplementation(`${apiBaseUrl}/api/v1/me/tenants`, {
        method: 'GET',
        headers: {
          Accept: 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        cache: 'no-store',
        credentials: 'omit',
        redirect: 'error',
        referrerPolicy: 'no-referrer',
      });

      if (!response.ok) {
        throw new MembershipBootstrapApiError(response.status);
      }

      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        throw new MembershipBootstrapApiError(response.status, 'invalid_response');
      }

      if (!isMembershipBootstrapResponse(payload)) {
        throw new MembershipBootstrapApiError(response.status, 'invalid_response');
      }

      return payload.memberships;
    },
  });
}
