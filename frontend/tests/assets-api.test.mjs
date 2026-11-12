import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import react from '@vitejs/plugin-react';
import { createServer } from 'vite';

let vite;
let createAssetInventoryClient;
let AssetInventoryApiError;

before(async () => {
  vite = await createServer({
    configFile: false,
    plugins: [react()],
    server: { middlewareMode: true, hmr: { port: 0 } },
    optimizeDeps: { noDiscovery: true },
    appType: 'custom',
  });
  ({ createAssetInventoryClient, AssetInventoryApiError } = await vite.ssrLoadModule('/src/api/assets.ts'));
});

after(async () => {
  await vite?.close();
});

const session = { accessToken: 'short-lived.test.token', tenantSlug: 'acme-security' };
const asset = {
  id: '8f3f6e2a-63c1-4d14-9b4c-1f4f0e3b2a11',
  tenant_id: '9f3f6e2a-63c1-4d14-9b4c-1f4f0e3b2a12',
  name: 'Production API',
  asset_type: 'application',
  external_id: 'svc-api-001',
  environment: 'production',
  criticality: 'critical',
  source: 'manual',
  status: 'active',
  created_at: '2026-11-12T10:00:00Z',
  updated_at: '2026-11-12T11:00:00Z',
};

test('asset client uses bearer auth and tenant slug without sending tenant UUIDs', async () => {
  let requestedUrl;
  let requestOptions;
  const client = createAssetInventoryClient('https://api.example.test', async (url, options) => {
    requestedUrl = url;
    requestOptions = options;
    return new Response(JSON.stringify([asset]), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  });

  const result = await client.listAssets(session, { includeArchived: true, limit: 25, offset: 50 });
  const url = new URL(requestedUrl);
  assert.equal(url.origin, 'https://api.example.test');
  assert.equal(url.pathname, '/api/v1/assets');
  assert.equal(url.searchParams.get('include_archived'), 'true');
  assert.equal(url.searchParams.get('limit'), '25');
  assert.equal(url.searchParams.get('offset'), '50');
  assert.equal(requestOptions.method, 'GET');
  assert.equal(requestOptions.headers.Authorization, 'Bearer short-lived.test.token');
  assert.equal(requestOptions.headers['X-AEGIS-Tenant'], 'acme-security');
  assert.equal(requestOptions.credentials, 'omit');
  assert.equal(requestOptions.redirect, 'error');
  assert.equal(requestOptions.cache, 'no-store');
  assert.equal(requestOptions.referrerPolicy, 'no-referrer');
  assert.equal(requestOptions.body, undefined);
  assert.equal(JSON.stringify(requestOptions).includes(asset.tenant_id), false);
  assert.equal(result[0].id, asset.id);
});

test('asset client rejects insecure non-loopback API origins', () => {
  assert.throws(() => createAssetInventoryClient('http://api.example.test'), /must use HTTPS/);
  assert.doesNotThrow(() => createAssetInventoryClient('http://127.0.0.1:8000'));
});

test('asset client rejects URL credentials, paths, queries and fragments', () => {
  for (const origin of [
    'https://user:password@api.example.test',
    'https://api.example.test/v1',
    'https://api.example.test?tenant=acme',
    'https://api.example.test#fragment',
  ]) {
    assert.throws(() => createAssetInventoryClient(origin), TypeError);
  }
});

test('asset client validates session and pagination before making a request', async () => {
  let calls = 0;
  const client = createAssetInventoryClient('https://api.example.test', async () => {
    calls += 1;
    return new Response('[]', { status: 200 });
  });

  await assert.rejects(client.listAssets({ accessToken: 'bad token', tenantSlug: 'acme-security' }), TypeError);
  await assert.rejects(client.listAssets({ accessToken: 'token', tenantSlug: 'invalid slug' }), TypeError);
  await assert.rejects(client.listAssets(session, { limit: 101 }), RangeError);
  await assert.rejects(client.listAssets(session, { offset: -1 }), RangeError);
  assert.equal(calls, 0);
});

test('asset client rejects unexpected fields and malformed records', async () => {
  const client = createAssetInventoryClient('https://api.example.test', async () =>
    new Response(JSON.stringify([{ ...asset, customer_email: 'private@example.test' }]), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    }),
  );

  await assert.rejects(
    client.listAssets(session),
    (error) => error instanceof AssetInventoryApiError && error.code === 'invalid_response',
  );
});

test('asset client does not expose backend error details to the browser', async () => {
  const client = createAssetInventoryClient('https://api.example.test', async () =>
    new Response(JSON.stringify({ detail: 'internal database connection string' }), {
      status: 403,
      headers: { 'content-type': 'application/json' },
    }),
  );

  await assert.rejects(
    client.listAssets(session),
    (error) =>
      error instanceof AssetInventoryApiError &&
      error.status === 403 &&
      !error.message.includes('database connection string'),
  );
});
