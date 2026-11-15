import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import react from '@vitejs/plugin-react';
import { createServer } from 'vite';

let vite;
let createMembershipBootstrapClient;
let MembershipBootstrapApiError;

before(async () => {
  vite = await createServer({
    configFile: false,
    plugins: [react()],
    server: { middlewareMode: true, hmr: false },
    optimizeDeps: { noDiscovery: true, include: [] },
    appType: 'custom',
  });

  ({ createMembershipBootstrapClient, MembershipBootstrapApiError } =
    await vite.ssrLoadModule('/src/api/membershipBootstrap.ts'));
});

after(async () => {
  await vite?.close();
});

const membership = {
  tenant_slug: 'northstar-security',
  display_name: 'Northstar Security',
  role: 'tenant_admin',
};

test('bootstrap requests only the verified subject endpoint with safe transport defaults', async () => {
  let capturedUrl;
  let capturedInit;
  const client = createMembershipBootstrapClient('https://api.aegis.invalid', async (url, init) => {
    capturedUrl = String(url);
    capturedInit = init;
    return new Response(JSON.stringify({ memberships: [membership] }), { status: 200 });
  });

  const result = await client.listMyMemberships('test-token-not-a-credential');

  assert.equal(capturedUrl, 'https://api.aegis.invalid/api/v1/me/tenants');
  assert.equal(capturedInit.method, 'GET');
  assert.equal(capturedInit.headers.Authorization, 'Bearer test-token-not-a-credential');
  assert.equal(capturedInit.headers.Accept, 'application/json');
  assert.equal(Object.hasOwn(capturedInit.headers, 'X-AEGIS-Tenant'), false);
  assert.equal(capturedInit.credentials, 'omit');
  assert.equal(capturedInit.redirect, 'error');
  assert.equal(capturedInit.cache, 'no-store');
  assert.equal(capturedInit.referrerPolicy, 'no-referrer');
  assert.deepEqual(result, [membership]);
  assert.equal(Object.hasOwn(result[0], 'tenant_id'), false);
});

test('bootstrap accepts an empty active-membership list', async () => {
  const client = createMembershipBootstrapClient('https://api.aegis.invalid', async () => (
    new Response(JSON.stringify({ memberships: [] }), { status: 200 })
  ));

  assert.deepEqual(await client.listMyMemberships('test-token-not-a-credential'), []);
});

test('bootstrap rejects untrusted origins and invalid tokens before network access', async () => {
  assert.throws(() => createMembershipBootstrapClient('http://api.aegis.invalid'), TypeError);
  assert.throws(() => createMembershipBootstrapClient('https://user:pass@api.aegis.invalid'), TypeError);
  assert.throws(() => createMembershipBootstrapClient('https://api.aegis.invalid/prefix'), TypeError);
  assert.doesNotThrow(() => createMembershipBootstrapClient('http://localhost:8000'));

  let calls = 0;
  const client = createMembershipBootstrapClient('https://api.aegis.invalid', async () => {
    calls += 1;
    return new Response(JSON.stringify({ memberships: [] }));
  });

  await assert.rejects(client.listMyMemberships(' '), TypeError);
  await assert.rejects(client.listMyMemberships('token\nwith-control'), TypeError);
  await assert.rejects(client.listMyMemberships('x'.repeat(8193)), TypeError);
  assert.equal(calls, 0);
});

test('bootstrap rejects duplicate slugs, unsupported roles and client-supplied tenant identifiers', async () => {
  const invalidPayloads = [
    { memberships: [{ ...membership, tenant_id: 'must-not-be-returned' }] },
    { memberships: [membership, membership] },
    { memberships: [{ ...membership, role: 'platform_admin' }] },
    { memberships: [{ ...membership, tenant_slug: 'Not A Slug' }] },
    { memberships: [{ ...membership, display_name: 'Northstar\nSecurity' }] },
    { memberships: Array.from({ length: 101 }, (_, index) => ({
      ...membership,
      tenant_slug: `tenant-${index}`,
    })) },
    { memberships: [], unexpected: true },
  ];

  for (const payload of invalidPayloads) {
    const client = createMembershipBootstrapClient('https://api.aegis.invalid', async () => (
      new Response(JSON.stringify(payload), { status: 200 })
    ));
    await assert.rejects(
      client.listMyMemberships('test-token-not-a-credential'),
      (error) => error instanceof MembershipBootstrapApiError &&
        error.code === 'invalid_response',
    );
  }
});

test('bootstrap sanitizes HTTP and JSON response errors', async () => {
  const failedClient = createMembershipBootstrapClient('https://api.aegis.invalid', async () => (
    new Response('database-password-must-not-appear', { status: 503 })
  ));
  await assert.rejects(
    failedClient.listMyMemberships('test-token-not-a-credential'),
    (error) => {
      assert.ok(error instanceof MembershipBootstrapApiError);
      assert.equal(error.status, 503);
      assert.doesNotMatch(error.message, /database-password/);
      return true;
    },
  );

  const malformedClient = createMembershipBootstrapClient('https://api.aegis.invalid', async () => (
    new Response('not-json', { status: 200 })
  ));
  await assert.rejects(
    malformedClient.listMyMemberships('test-token-not-a-credential'),
    (error) => error instanceof MembershipBootstrapApiError &&
      error.code === 'invalid_response',
  );
});
