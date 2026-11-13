import type { TenantSession } from './tenantProfile';

export const ASSET_TYPES = [
  'cloud_account',
  'endpoint',
  'server',
  'domain',
  'repository',
  'network',
  'application',
  'database',
  'user_identity',
  'other',
] as const;

export const ASSET_ENVIRONMENTS = [
  'production',
  'staging',
  'development',
  'test',
  'unknown',
] as const;

export const ASSET_CRITICALITIES = ['critical', 'high', 'medium', 'low'] as const;

export type AssetType = (typeof ASSET_TYPES)[number];
export type AssetEnvironment = (typeof ASSET_ENVIRONMENTS)[number];
export type AssetCriticality = (typeof ASSET_CRITICALITIES)[number];
export type AssetStatus = 'active' | 'archived';

export interface AssetSession extends TenantSession {
  /**
   * A display hint supplied by a future server-verified membership bootstrap.
   * It is never read from user input or trusted as an authorization control.
   */
  membershipRole?: string;
}

export interface AssetRecord {
  id: string;
  tenant_id: string;
  name: string;
  asset_type: AssetType;
  external_id: string | null;
  environment: AssetEnvironment;
  criticality: AssetCriticality;
  source: string;
  status: AssetStatus;
  created_at: string;
  updated_at: string;
}

export interface AssetCreateInput {
  name: string;
  asset_type: AssetType;
  external_id?: string | null;
  environment: AssetEnvironment;
  criticality: AssetCriticality;
}

export interface AssetUpdateInput {
  name?: string;
  asset_type?: AssetType;
  external_id?: string | null;
  environment?: AssetEnvironment;
  criticality?: AssetCriticality;
  status?: AssetStatus;
}

export interface AssetListOptions {
  limit?: number;
  offset?: number;
  includeArchived?: boolean;
}

type FetchImplementation = typeof fetch;

export class AssetApiError extends Error {
  readonly status: number;
  readonly code: 'request_failed' | 'invalid_response';

  constructor(status: number, code: 'request_failed' | 'invalid_response' = 'request_failed') {
    super(code === 'invalid_response'
      ? 'The asset service returned an invalid response.'
      : 'The asset request failed.');
    this.name = 'AssetApiError';
    this.status = status;
    this.code = code;
  }
}

const TENANT_SLUG_PATTERN = /^[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const UPDATE_FIELDS = new Set(['name', 'asset_type', 'external_id', 'environment', 'criticality', 'status']);

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

function normalizeSession(session: TenantSession): { accessToken: string; tenantSlug: string } {
  const accessToken = session.accessToken.trim();
  const tenantSlug = session.tenantSlug.trim();

  if (accessToken.length === 0 || accessToken.length > 8192) {
    throw new TypeError('A valid short-lived access token is required.');
  }
  if (!TENANT_SLUG_PATTERN.test(tenantSlug)) {
    throw new TypeError('A valid tenant slug is required.');
  }

  return { accessToken, tenantSlug };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isOneOf<const T extends readonly string[]>(values: T, value: unknown): value is T[number] {
  return typeof value === 'string' && (values as readonly string[]).includes(value);
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
    typeof value.name === 'string' && value.name.trim().length > 0 &&
    isOneOf(ASSET_TYPES, value.asset_type) &&
    (value.external_id === null || typeof value.external_id === 'string') &&
    isOneOf(ASSET_ENVIRONMENTS, value.environment) &&
    isOneOf(ASSET_CRITICALITIES, value.criticality) &&
    typeof value.source === 'string' && value.source.trim().length > 0 &&
    (value.status === 'active' || value.status === 'archived') &&
    typeof value.created_at === 'string' && Number.isFinite(Date.parse(value.created_at)) &&
    typeof value.updated_at === 'string' && Number.isFinite(Date.parse(value.updated_at))
  );
}

function isAssetList(value: unknown): value is AssetRecord[] {
  return Array.isArray(value) && value.every(isAssetRecord);
}

function normalizeUpdate(input: AssetUpdateInput): AssetUpdateInput {
  if (Object.keys(input).some((key) => !UPDATE_FIELDS.has(key))) {
    throw new TypeError('Unsupported asset update field.');
  }

  const payload: AssetUpdateInput = {};
  if (input.name !== undefined) {
    const name = input.name.trim();
    if (!name || name.length > 160) throw new TypeError('Asset name must contain 1 to 160 characters.');
    payload.name = name;
  }
  if (input.asset_type !== undefined) {
    if (!isOneOf(ASSET_TYPES, input.asset_type)) throw new TypeError('Asset type is invalid.');
    payload.asset_type = input.asset_type;
  }
  if (input.external_id !== undefined) {
    const externalId = input.external_id?.trim() || null;
    if (externalId && externalId.length > 160) throw new TypeError('External asset identifier is too long.');
    payload.external_id = externalId;
  }
  if (input.environment !== undefined) {
    if (!isOneOf(ASSET_ENVIRONMENTS, input.environment)) throw new TypeError('Asset environment is invalid.');
    payload.environment = input.environment;
  }
  if (input.criticality !== undefined) {
    if (!isOneOf(ASSET_CRITICALITIES, input.criticality)) throw new TypeError('Asset criticality is invalid.');
    payload.criticality = input.criticality;
  }
  if (input.status !== undefined) {
    if (input.status !== 'active' && input.status !== 'archived') throw new TypeError('Asset status is invalid.');
    payload.status = input.status;
  }
  if (Object.keys(payload).length === 0) throw new TypeError('At least one asset field must be updated.');
  return payload;
}

export function createAssetClient(
  baseUrl: string,
  fetchImplementation: FetchImplementation = fetch,
) {
  const apiBaseUrl = normalizeBaseUrl(baseUrl);

  async function request(path: string, session: TenantSession, init: RequestInit = {}): Promise<unknown> {
    const identity = normalizeSession(session);
    const response = await fetchImplementation(apiBaseUrl + path, {
      ...init,
      headers: {
        Accept: 'application/json',
        Authorization: 'Bearer ' + identity.accessToken,
        'X-AEGIS-Tenant': identity.tenantSlug,
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      },
      cache: 'no-store',
      credentials: 'omit',
      redirect: 'error',
      referrerPolicy: 'no-referrer',
    });

    if (!response.ok) throw new AssetApiError(response.status);

    try {
      return await response.json();
    } catch {
      throw new AssetApiError(response.status, 'invalid_response');
    }
  }

  return Object.freeze({
    async listAssets(session: TenantSession, options: AssetListOptions = {}): Promise<AssetRecord[]> {
      const limit = options.limit ?? 50;
      const offset = options.offset ?? 0;
      const includeArchived = options.includeArchived ?? false;

      if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
        throw new TypeError('Asset page size must be between 1 and 100.');
      }
      if (!Number.isInteger(offset) || offset < 0) {
        throw new TypeError('Asset offset must be a non-negative integer.');
      }

      const query = new URLSearchParams({
        limit: String(limit),
        offset: String(offset),
        include_archived: String(includeArchived),
      });
      const payload = await request('/api/v1/assets?' + query.toString(), session);

      if (!isAssetList(payload)) throw new AssetApiError(200, 'invalid_response');
      return payload;
    },

    async createAsset(session: TenantSession, input: AssetCreateInput): Promise<AssetRecord> {
      const name = input.name.trim();
      if (!name || name.length > 160) throw new TypeError('Asset name must contain 1 to 160 characters.');
      if (!isOneOf(ASSET_TYPES, input.asset_type) ||
          !isOneOf(ASSET_ENVIRONMENTS, input.environment) ||
          !isOneOf(ASSET_CRITICALITIES, input.criticality)) {
        throw new TypeError('Asset classification is invalid.');
      }
      const externalId = input.external_id?.trim() || null;
      if (externalId && externalId.length > 160) throw new TypeError('External asset identifier is too long.');

      const payload = await request('/api/v1/assets', session, {
        method: 'POST',
        body: JSON.stringify({
          name,
          asset_type: input.asset_type,
          external_id: externalId,
          environment: input.environment,
          criticality: input.criticality,
        }),
      });

      if (!isAssetRecord(payload)) throw new AssetApiError(201, 'invalid_response');
      return payload;
    },

    async updateAsset(session: TenantSession, assetId: string, input: AssetUpdateInput): Promise<AssetRecord> {
      if (!UUID_PATTERN.test(assetId)) throw new TypeError('A valid asset identifier is required.');
      const update = normalizeUpdate(input);
      const payload = await request('/api/v1/assets/' + assetId, session, {
        method: 'PATCH',
        body: JSON.stringify(update),
      });

      if (!isAssetRecord(payload)) throw new AssetApiError(200, 'invalid_response');
      return payload;
    },
  });
}
