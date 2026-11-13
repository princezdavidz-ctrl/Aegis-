import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import react from '@vitejs/plugin-react';
import { createServer } from 'vite';

let vite;
let createAssetClient;
let AssetApiError;

before(async () => {
  vite = await createServer({
    configFile: false,
    plugins: [react()],
    server: { middlewareMode: true, hmr: false },
    optimizeDeps: { noDiscovery: true, include: [] },
    appType: 'custom',
  });

  ({ createAssetClient, AssetApiError } = await vite.ssrLoadModule('/src/api/assets.ts'));
});

after(async () => {
  await vite?.close();
});

const asset = {
  id: 'd8a3e9c4-7b5d-4c0f-9d6e-1b2c3d4e5f60',
  tenant_id: 'f5d4c3b2-a190-4e8d-9c7b-6a5f4e3d2c10',
  name: 'Production API',
  asset_type: 'application',
  external_id: 'svc-api-001',
  environment: 'production',
  criticality: 'critical',
  source: 'manual',
  status: 'active',
  created_at: '2026-11-12T10:00:00Z',
  updated_at: '2026-11-12T10:00:00Z',
};

const session = {
  accessToken: 'test-token-not-a-credential',
  tenantSlug: 'northstar-security',
};

test('asset list uses the fixed tenant-scoped endpoint and safe request defaults', async () => {
  let capturedUrl;
  let capturedInit;
  const client = createAssetClient('https://api.aegis.invalid', async (url, init) => {
    capturedUrl = String(url);
    capturedInit = init;
    return new Response(JSON.stringify([asset]), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  });

  const result = await client.listAssets(session, { limit: 50, offset: 100, includeArchived: true });

  assert.equal(capturedUrl, 'https://api.aegis.invalid/api/v1/assets?limit=50&offset=100&include_archived=true');
  assert.equal(capturedInit.method, undefined);
  assert.equal(capturedInit.headers.Authorization, 'Bearer test-token-not-a-credential');
  assert.equal(capturedInit.headers['X-AEGIS-Tenant'], 'northstar-security');
  assert.equal(capturedInit.credentials, 'omit');
  assert.equal(capturedInit.redirect, 'error');
  assert.equal(capturedInit.cache, 'no-store');
  assert.equal(result[0].name, 'Production API');
  assert.equal(capturedUrl.includes(asset.tenant_id), false);
});

test('asset client rejects invalid tenant context and pagination before network access', async () => {
  let calls = 0;
  const client = createAssetClient('https://api.aegis.invalid', async () => {
    calls += 1;
    return new Response(JSON.stringify([asset]));
  });

  await assert.rejects(client.listAssets({ accessToken: ' ', tenantSlug: 'northstar-security' }), TypeError);
  await assert.rejects(client.listAssets(session, { limit: 101 }), TypeError);
  await assert.rejects(client.listAssets(session, { offset: -1 }), TypeError);
  assert.equal(calls, 0);
});

test('asset client rejects insecure or credential-bearing API origins', () => {
  assert.throws(() => createAssetClient('http://api.aegis.invalid'), TypeError);
  assert.throws(() => createAssetClient('https://user:pass@api.aegis.invalid'), TypeError);
  assert.throws(() => createAssetClient('https://api.aegis.invalid/prefix'), TypeError);
  assert.doesNotThrow(() => createAssetClient('http://localhost:8000'));
});

test('asset registration sends only validated asset fields and never a tenant UUID', async () => {
  let capturedUrl;
  let capturedInit;
  const client = createAssetClient('https://api.aegis.invalid', async (url, init) => {
    capturedUrl = String(url);
    capturedInit = init;
    return new Response(JSON.stringify(asset), { status: 201 });
  });

  await client.createAsset(session, {
    name: '  Production API  ',
    asset_type: 'application',
    external_id: ' svc-api-001 ',
    environment: 'production',
    criticality: 'critical',
  });

  assert.equal(capturedUrl, 'https://api.aegis.invalid/api/v1/assets');
  assert.equal(capturedInit.method, 'POST');
  assert.deepEqual(JSON.parse(capturedInit.body), {
    name: 'Production API',
    asset_type: 'application',
    external_id: 'svc-api-001',
    environment: 'production',
    criticality: 'critical',
  });
  assert.equal(Object.hasOwn(JSON.parse(capturedInit.body), 'tenant_id'), false);
});

test('asset status updates require a UUID and use the fixed PATCH route', async () => {
  let capturedUrl;
  let capturedInit;
  const client = createAssetClient('https://api.aegis.invalid', async (url, init) => {
    capturedUrl = String(url);
    capturedInit = init;
    return new Response(JSON.stringify({ ...asset, status: 'archived' }), { status: 200 });
  });

  const result = await client.updateAsset(session, asset.id, { status: 'archived' });
  assert.equal(capturedUrl, 'https://api.aegis.invalid/api/v1/assets/' + asset.id);
  assert.equal(capturedInit.method, 'PATCH');
  assert.deepEqual(JSON.parse(capturedInit.body), { status: 'archived' });
  assert.equal(result.status, 'archived');
  await assert.rejects(client.updateAsset(session, 'not-a-uuid', { status: 'archived' }), TypeError);
});

test('asset update drops unsupported fields and rejects empty updates', async () => {
  let capturedBody;
  const client = createAssetClient('https://api.aegis.invalid', async (_url, init) => {
    capturedBody = init.body;
    return new Response(JSON.stringify(asset), { status: 200 });
  });

  await assert.rejects(
    client.updateAsset(session, asset.id, { status: 'archived', tenant_id: asset.tenant_id }),
    TypeError,
  );
  await assert.rejects(client.updateAsset(session, asset.id, {}), TypeError);
  assert.equal(capturedBody, undefined);
});

test('asset client rejects unexpected response fields and sanitizes HTTP failures', async () => {
  const invalidClient = createAssetClient('https://api.aegis.invalid', async () => (
    new Response(JSON.stringify([{ ...asset, secret: 'must-not-be-accepted' }]), { status: 200 })
  ));
  await assert.rejects(
    invalidClient.listAssets(session),
    (error) => error instanceof AssetApiError && error.code === 'invalid_response',
  );

  const failedClient = createAssetClient('https://api.aegis.invalid', async () => (
    new Response('database-password-must-not-appear', { status: 503 })
  ));
  await assert.rejects(
    failedClient.listAssets(session),
    (error) => {
      assert.ok(error instanceof AssetApiError);
      assert.equal(error.status, 503);
      assert.doesNotMatch(error.message, /database-password/);
      return true;
    },
  );
});
