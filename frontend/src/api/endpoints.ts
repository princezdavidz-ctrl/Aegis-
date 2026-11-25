import type { TenantSession } from './tenantProfile';

export type EndpointPlatform = 'windows' | 'linux' | 'macos';
export type EndpointStatus = 'active' | 'revoked';
export type EndpointHealthStatus = 'online' | 'stale' | 'offline' | 'never_reported' | 'revoked';

export interface EndpointDevice {
  device_id: string;
  platform: EndpointPlatform;
  hostname: string;
  agent_version: string;
  status: EndpointStatus;
  enrolled_at: string;
  last_seen_at: string | null;
  last_heartbeat_at: string | null;
  health_status: EndpointHealthStatus;
  last_sequence: number;
  revoked_at: string | null;
  last_event_type: string | null;
  last_event_received_at: string | null;
}

export interface EndpointFleet {
  items: EndpointDevice[];
  limit: number;
}

export interface EndpointInvitation {
  invitation_id: string;
  platform: EndpointPlatform;
  expires_at: string;
  enrollment_token: string;
}

type FetchImplementation = typeof fetch;

export class EndpointApiError extends Error {
  readonly status: number;
  readonly code: 'request_failed' | 'invalid_response';

  constructor(status: number, code: 'request_failed' | 'invalid_response' = 'request_failed') {
    super(code === 'invalid_response'
      ? 'The endpoint service returned an invalid response.'
      : 'The endpoint request failed.');
    this.name = 'EndpointApiError';
    this.status = status;
    this.code = code;
  }
}

const TENANT_SLUG_PATTERN = /^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const PLATFORMS = new Set<EndpointPlatform>(['windows', 'linux', 'macos']);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNullableDate(value: unknown): value is string | null {
  return value === null || (typeof value === 'string' && Number.isFinite(Date.parse(value)));
}

function isDevice(value: unknown): value is EndpointDevice {
  if (!isRecord(value)) return false;
  const allowed = new Set([
    'device_id', 'platform', 'hostname', 'agent_version', 'status', 'enrolled_at',
    'last_seen_at', 'last_heartbeat_at', 'health_status', 'last_sequence', 'last_event_type', 'last_event_received_at',
  ]);
  return !Object.keys(value).some((key) => !allowed.has(key)) &&
    typeof value.device_id === 'string' && UUID_PATTERN.test(value.device_id) &&
    typeof value.platform === 'string' && PLATFORMS.has(value.platform as EndpointPlatform) &&
    typeof value.hostname === 'string' && value.hostname.trim().length > 0 &&
    typeof value.agent_version === 'string' &&
    (value.status === 'active' || value.status === 'revoked') &&
    typeof value.enrolled_at === 'string' && Number.isFinite(Date.parse(value.enrolled_at)) &&
    isNullableDate(value.last_seen_at) && isNullableDate(value.last_heartbeat_at) &&
    ['online', 'stale', 'offline', 'never_reported', 'revoked'].includes(String(value.health_status)) &&
    Number.isInteger(value.last_sequence) &&
    Number(value.last_sequence) >= 0 && isNullableDate(value.revoked_at) &&
    (value.last_event_type === null || typeof value.last_event_type === 'string') &&
    isNullableDate(value.last_event_received_at);
}

function normalizeIdentity(session: TenantSession): { token: string; tenant: string } {
  const token = session.accessToken.trim();
  const tenant = session.tenantSlug.trim();
  if (!token || token.length > 8192) throw new TypeError('A valid short-lived access token is required.');
  if (!TENANT_SLUG_PATTERN.test(tenant)) throw new TypeError('A valid tenant slug is required.');
  return { token, tenant };
}

export function createEndpointClient(baseUrl: string, fetchImplementation: FetchImplementation = fetch) {
  let origin: string;
  try {
    const url = new URL(baseUrl);
    const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
    if (!(url.protocol === 'https:' || (url.protocol === 'http:' && loopback)) ||
        url.username || url.password || url.search || url.hash || (url.pathname && url.pathname !== '/')) {
      throw new TypeError();
    }
    origin = url.origin;
  } catch {
    throw new TypeError('The AEGIS API base URL must be an HTTPS origin (HTTP is allowed only for loopback development).');
  }

  async function request(path: string, session: TenantSession, init: RequestInit = {}): Promise<unknown> {
    const identity = normalizeIdentity(session);
    const response = await fetchImplementation(origin + path, {
      ...init,
      headers: {
        Accept: 'application/json',
        Authorization: 'Bearer ' + identity.token,
        'X-AEGIS-Tenant': identity.tenant,
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      },
      cache: 'no-store',
      credentials: 'omit',
      redirect: 'error',
      referrerPolicy: 'no-referrer',
    });
    if (!response.ok) throw new EndpointApiError(response.status);
    try {
      return await response.json();
    } catch {
      throw new EndpointApiError(response.status, 'invalid_response');
    }
  }

  return Object.freeze({
    async listDevices(session: TenantSession, limit = 100): Promise<EndpointFleet> {
      if (!Number.isInteger(limit) || limit < 1 || limit > 500) {
        throw new TypeError('Endpoint page size must be between 1 and 500.');
      }
      const payload = await request('/api/v1/endpoints/devices?limit=' + limit, session);
      if (!isRecord(payload) || Object.keys(payload).some((key) => !['items', 'limit'].includes(key)) ||
          !Array.isArray(payload.items) || !payload.items.every(isDevice) || payload.limit !== limit) {
        throw new EndpointApiError(200, 'invalid_response');
      }
      return payload as unknown as EndpointFleet;
    },

    async createInvitation(session: TenantSession, platform: EndpointPlatform, ttlMinutes = 60): Promise<EndpointInvitation> {
      if (!PLATFORMS.has(platform) || !Number.isInteger(ttlMinutes) || ttlMinutes < 5 || ttlMinutes > 1440) {
        throw new TypeError('Invitation platform or expiry is invalid.');
      }
      const payload = await request('/api/v1/endpoints/invitations', session, {
        method: 'POST',
        body: JSON.stringify({ platform, ttl_minutes: ttlMinutes }),
      });
      if (!isRecord(payload) || Object.keys(payload).some((key) =>
        !['invitation_id', 'platform', 'expires_at', 'enrollment_token'].includes(key)) ||
        typeof payload.invitation_id !== 'string' || !UUID_PATTERN.test(payload.invitation_id) ||
        payload.platform !== platform || typeof payload.expires_at !== 'string' ||
        !Number.isFinite(Date.parse(payload.expires_at)) ||
        typeof payload.enrollment_token !== 'string' ||
        payload.enrollment_token.length < 32 || payload.enrollment_token.length > 256) {
        throw new EndpointApiError(200, 'invalid_response');
      }
      return payload as unknown as EndpointInvitation;
    },

    async revokeDevice(session: TenantSession, deviceId: string): Promise<void> {
      if (!UUID_PATTERN.test(deviceId)) throw new TypeError('A valid endpoint device identifier is required.');
      await request('/api/v1/endpoints/' + deviceId + '/revoke', session, { method: 'POST' });
    },
  });
}
