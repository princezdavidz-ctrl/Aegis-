import type { TenantSession } from './tenantSession';

export type AssetType =
  | 'cloud_account' | 'endpoint' | 'server' | 'domain' | 'repository'
  | 'network' | 'application' | 'database' | 'user_identity' | 'other';
export type AssetEnvironment = 'production' | 'staging' | 'development' | 'test' | 'unknown';
export type AssetCriticality = 'critical' | 'high' | 'medium' | 'low';
export type AssetStatus = 'active' | 'archived';

export interface AssetRecord {
  readonly id: string;
  readonly tenant_id: string;
  readonly name: string;
  readonly asset_type: AssetType;
  readonly external_id: string | null;
  readonly environment: AssetEnvironment;
  readonly criticality: AssetCriticality;
  readonly source: string;
  readonly status: AssetStatus;
  readonly created_at: string;
  readonly updated_at: string;
}

export interface AssetListOptions {
  readonly includeArchived?: boolean;
  readonly limit?: number;
  readonly offset?: number;
}

export class AssetInventoryApiError extends Error {
  readonly status: number;
  readonly code: 'request_failed' | 'invalid_response';

  constructor(status: number, code: 'request_failed' | 'invalid_response' = 'request_failed') {
    super(code === 'invalid_response'
      ? 'The asset inventory service returned an invalid response.'
      : 'The asset inventory request failed.');
    this.name = 'AssetInventoryApiError';
    this.status = status;
    this.code = code;
  }
}

const TENANT_SLUG_PATTERN = /^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const ASSET_TYPES = new Set<AssetType>([
  'cloud_account', 'endpoint', 'server', 'domain', 'repository',
  'network', 'application', 'database', 'user_identity', 'other',
]);
const ENVIRONMENTS = new Set<AssetEnvironment>([
  'production', 'staging', 'development', 'test', 'unknown',
]);
const CRITICALITIES = new Set<AssetCriticality>(['critical', 'high', 'medium', 'low']);

function normalizeApiOrigin(value: string): string {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new TypeError('A valid AEGIS API origin is required.');
  }

  const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  const secureTransport = url.protocol === 'https:' || (url.protocol === 'http:' && loopback);
  if (
    !secureTransport ||
    url.username.length > 0 ||
    url.password.length > 0 ||
    url.search.length > 0 ||
    url.hash.length > 0 ||
    (url.pathname !== '' && url.pathname !== '/')
  ) {
    throw new TypeError(
      'The AEGIS API origin must use HTTPS (HTTP is allowed only for loopback development).',
    );
  }
  return url.origin;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isTimestamp(value: unknown): value is string {
  return typeof value === 'string' &&
    /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) &&
    Number.isFinite(Date.parse(value));
}

function isAssetRecord(value: unknown): value is AssetRecord {
  if (!isRecord(value)) return false;
  const allowedKeys = new Set([
    'id', 'tenant_id', 'name', 'asset_type', 'external_id', 'environment',
    'criticality', 'source', 'status', 'created_at', 'updated_at',
  ]);
  if (Object.keys(value).some((key) => !allowedKeys.has(key))) return false;

  return (
    typeof value.id === 'string' && UUID_PATTERN.test(value.id) &&
    typeof value.tenant_id === 'string' && UUID_PATTERN.test(value.tenant_id) &&
    typeof value.name === 'string' && value.name.trim().length > 0 && value.name.length <= 160 &&
    typeof value.asset_type === 'string' && ASSET_TYPES.has(value.asset_type as AssetType) &&
    (value.external_id === null ||
      (typeof value.external_id === 'string' &&
        value.external_id.trim().length > 0 && value.external_id.length <= 160)) &&
    typeof value.environment === 'string' && ENVIRONMENTS.has(value.environment as AssetEnvironment) &&
    typeof value.criticality === 'string' && CRITICALITIES.has(value.criticality as AssetCriticality) &&
    typeof value.source === 'string' && value.source.length > 0 && value.source.length <= 32 &&
    (value.status === 'active' || value.status === 'archived') &&
    isTimestamp(value.created_at) && isTimestamp(value.updated_at)
  );
}

export function createAssetInventoryClient(
  apiOrigin: string,
  fetchImplementation: typeof fetch = fetch,
) {
  const baseUrl = normalizeApiOrigin(apiOrigin);

  return Object.freeze({
    async listAssets(
      session: TenantSession,
      options: AssetListOptions = {},
    ): Promise<AssetRecord[]> {
      if (
        !session ||
        typeof session.accessToken !== 'string' ||
        typeof session.tenantSlug !== 'string'
      ) {
        throw new TypeError('A verified short-lived access token and tenant selector are required.');
      }

      const accessToken = session.accessToken.trim();
      const tenantSlug = session.tenantSlug.trim();
      const limit = options.limit ?? 50;
      const offset = options.offset ?? 0;
      const includeArchived = options.includeArchived ?? false;

      if (accessToken.length === 0 || accessToken.length > 8192 || /\s/.test(accessToken)) {
        throw new TypeError('A valid short-lived access token is required.');
      }
      if (!TENANT_SLUG_PATTERN.test(tenantSlug)) {
        throw new TypeError('A valid tenant slug is required.');
      }
      if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
        throw new RangeError('Asset page size must be between 1 and 100.');
      }
      if (!Number.isSafeInteger(offset) || offset < 0 || offset > 1_000_000) {
        throw new RangeError('Asset page offset is outside the supported range.');
      }
      if (typeof includeArchived !== 'boolean') {
        throw new TypeError('includeArchived must be a boolean.');
      }

      const endpoint = new URL('/api/v1/assets', baseUrl);
      endpoint.searchParams.set('include_archived', String(includeArchived));
      endpoint.searchParams.set('limit', String(limit));
      endpoint.searchParams.set('offset', String(offset));

      const response = await fetchImplementation(endpoint.toString(), {
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

      if (!response.ok) throw new AssetInventoryApiError(response.status);

      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        throw new AssetInventoryApiError(response.status, 'invalid_response');
      }

      if (!Array.isArray(payload) || payload.length > limit || !payload.every(isAssetRecord)) {
        throw new AssetInventoryApiError(response.status, 'invalid_response');
      }
      return payload;
    },
  });
}
