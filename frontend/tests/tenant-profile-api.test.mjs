import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import react from '@vitejs/plugin-react';
import { createServer } from 'vite';

let vite;
let createTenantProfileClient;
let TenantProfileApiError;

before(async () => {
  vite = await createServer({
    configFile: false,
    plugins: [react()],
    server: { middlewareMode: true },
    appType: 'custom',
  });

  ({ createTenantProfileClient, TenantProfileApiError } = await vite.ssrLoadModule('/src/api/tenantProfile.ts'));
});

after(async () => {
  await vite?.close();
});

const profile = {
  id: 'd8a3e9c4-7b5d-4c0f-9d6e-1b2c3d4e5f60',
  slug: 'northstar-security',
  display_name: 'Northstar Security',
  industry: 'Technology',
  organization_size: '11-50',
  region: 'Africa',
  data_retention_days: 365,
  policy_profile: 'baseline',
  created_at: '2026-11-10T12:00:00Z',
};

test('tenant profile client sends bearer identity and selected tenant slug to the fixed endpoint', async () => {
  let capturedUrl;
  let capturedInit;

  const client = createTenantProfileClient('https://api.aegis.invalid', async (url, init) => {
    capturedUrl = String(url);
    capturedInit = init;
    return new Response(JSON.stringify(profile), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  });

  const result = await client.getProfile({
    accessToken: 'test-token-not-a-credential',
    tenantSlug: 'northstar-security',
  });

  assert.equal(capturedUrl, 'https://api.aegis.invalid/api/v1/tenants/profile');
  assert.equal(capturedInit.method, 'GET');
  assert.equal(capturedInit.headers.Authorization, 'Bearer test-token-not-a-credential');
  assert.equal(capturedInit.headers['X-AEGIS-Tenant'], 'northstar-security');
  assert.equal(capturedInit.credentials, 'omit');
  assert.equal(capturedInit.redirect, 'error');
  assert.equal(capturedInit.cache, 'no-store');
  assert.equal(result.slug, 'northstar-security');
});

test('tenant profile client rejects invalid identity context before making a request', async () => {
  let calls = 0;
  const client = createTenantProfileClient('https://api.aegis.invalid', async () => {
    calls += 1;
    return new Response(JSON.stringify(profile));
  });

  await assert.rejects(
    client.getProfile({ accessToken: ' ', tenantSlug: 'northstar-security' }),
    TypeError,
  );
  await assert.rejects(
    client.getProfile({ accessToken: 'test-token-not-a-credential', tenantSlug: 'not valid' }),
    TypeError,
  );
  assert.equal(calls, 0);
});

test('tenant profile client rejects insecure non-loopback API origins', () => {
  assert.throws(() => createTenantProfileClient('http://api.aegis.invalid'), TypeError);
  assert.throws(() => createTenantProfileClient('https://user:pass@api.aegis.invalid'), TypeError);
  assert.throws(() => createTenantProfileClient('https://api.aegis.invalid/prefix'), TypeError);
  assert.doesNotThrow(() => createTenantProfileClient('http://localhost:8000'));
});

test('tenant profile client sanitizes HTTP failures and does not expose response bodies', async () => {
  const client = createTenantProfileClient('https://api.aegis.invalid', async () => (
    new Response('database-password-must-not-appear', { status: 503 })
  ));

  await assert.rejects(
    client.getProfile({ accessToken: 'test-token-not-a-credential', tenantSlug: 'northstar-security' }),
    (error) => {
      assert.ok(error instanceof TenantProfileApiError);
      assert.equal(error.status, 503);
      assert.doesNotMatch(error.message, /database-password/);
      return true;
    },
  );
});

test('tenant profile client rejects malformed service responses', async () => {
  const client = createTenantProfileClient('https://api.aegis.invalid', async () => (
    new Response(JSON.stringify({ ...profile, tenant_id: 'client-supplied' }), { status: 200 })
  ));

  await assert.rejects(
    client.getProfile({ accessToken: 'test-token-not-a-credential', tenantSlug: 'northstar-security' }),
    (error) => error instanceof TenantProfileApiError && error.code === 'invalid_response',
  );
});
