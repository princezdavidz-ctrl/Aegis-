import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import react from '@vitejs/plugin-react';
import { createServer } from 'vite';

let vite;
let createMembershipClient;
let MembershipApiError;

before(async () => {
  vite = await createServer({
    configFile: false,
    plugins: [react()],
    server: { middlewareMode: true, hmr: false },
    optimizeDeps: { noDiscovery: true, include: [] },
    appType: 'custom',
  });

  ({ createMembershipClient, MembershipApiError } = await vite.ssrLoadModule('/src/api/memberships.ts'));
});

after(async () => {
  await vite?.close();
});

const session = {
  accessToken: 'test-token-not-a-credential',
  tenantSlug: 'northstar-security',
};

const member = {
  id: 'd8a3e9c4-7b5d-4c0f-9d6e-1b2c3d4e5f60',
  subject: 'oidc|existing-user',
  role: 'viewer',
  status: 'pending',
  created_at: '2026-11-13T10:00:00Z',
  invitation_expires_at: '2026-11-20T10:00:00Z',
};

const actionResult = {
  id: member.id,
  subject: member.subject,
  role: 'analyst',
  status: 'pending',
};

test('member listing uses the fixed tenant-scoped route and safe request defaults', async () => {
  let capturedUrl;
  let capturedInit;
  const client = createMembershipClient('https://api.aegis.invalid', async (url, init) => {
    capturedUrl = String(url);
    capturedInit = init;
    return new Response(JSON.stringify([member]), { status: 200 });
  });

  const result = await client.listMembers(session);

  assert.equal(capturedUrl, 'https://api.aegis.invalid/api/v1/tenants/members');
  assert.equal(capturedInit.method, 'GET');
  assert.equal(capturedInit.headers.Authorization, 'Bearer test-token-not-a-credential');
  assert.equal(capturedInit.headers['X-AEGIS-Tenant'], 'northstar-security');
  assert.equal(capturedInit.credentials, 'omit');
  assert.equal(capturedInit.redirect, 'error');
  assert.equal(capturedInit.cache, 'no-store');
  assert.equal(capturedInit.referrerPolicy, 'no-referrer');
  assert.equal(result[0].subject, 'oidc|existing-user');
  assert.equal(capturedUrl.includes('tenant_id'), false);
});

test('invitation sends only the existing OIDC subject and an assignable role', async () => {
  let capturedUrl;
  let capturedInit;
  const client = createMembershipClient('https://api.aegis.invalid', async (url, init) => {
    capturedUrl = String(url);
    capturedInit = init;
    return new Response(JSON.stringify(actionResult), { status: 201 });
  });

  const result = await client.inviteMember(session, {
    subject: '  oidc|existing-user  ',
    role: 'analyst',
  });

  assert.equal(capturedUrl, 'https://api.aegis.invalid/api/v1/tenants/members/invitations');
  assert.equal(capturedInit.method, 'POST');
  assert.deepEqual(JSON.parse(capturedInit.body), {
    subject: 'oidc|existing-user',
    role: 'analyst',
  });
  assert.equal(Object.hasOwn(JSON.parse(capturedInit.body), 'tenant_id'), false);
  assert.equal(result.status, 'pending');
});

test('membership updates encode opaque subjects and send only the requested action', async () => {
  let capturedUrl;
  let capturedInit;
  const client = createMembershipClient('https://api.aegis.invalid', async (url, init) => {
    capturedUrl = String(url);
    capturedInit = init;
    return new Response(JSON.stringify(actionResult), { status: 200 });
  });

  await client.updateMember(session, 'oidc|user/42', { action: 'change_role', role: 'security_manager' });

  assert.equal(
    capturedUrl,
    'https://api.aegis.invalid/api/v1/tenants/members/oidc%7Cuser%2F42',
  );
  assert.equal(capturedInit.method, 'PATCH');
  assert.deepEqual(JSON.parse(capturedInit.body), {
    action: 'change_role',
    role: 'security_manager',
  });

  await client.updateMember(session, 'oidc|existing-user', { action: 'suspend' });
  assert.deepEqual(JSON.parse(capturedInit.body), { action: 'suspend' });
});

test('membership client rejects invalid origins, sessions, subjects and privileged role assignment before network access', async () => {
  assert.throws(() => createMembershipClient('http://api.aegis.invalid'), TypeError);
  assert.throws(() => createMembershipClient('https://user:pass@api.aegis.invalid'), TypeError);
  assert.throws(() => createMembershipClient('https://api.aegis.invalid/prefix'), TypeError);
  assert.doesNotThrow(() => createMembershipClient('http://localhost:8000'));

  let calls = 0;
  const client = createMembershipClient('https://api.aegis.invalid', async () => {
    calls += 1;
    return new Response(JSON.stringify([member]));
  });

  await assert.rejects(client.listMembers({ accessToken: ' ', tenantSlug: 'northstar-security' }), TypeError);
  await assert.rejects(client.listMembers({ accessToken: session.accessToken, tenantSlug: 'not valid' }), TypeError);
  await assert.rejects(client.inviteMember(session, { subject: '  ', role: 'viewer' }), TypeError);
  await assert.rejects(client.inviteMember(session, { subject: 'oidc|user\n42', role: 'viewer' }), TypeError);
  await assert.rejects(client.inviteMember(session, { subject: 'oidc|user', role: 'tenant_admin' }), TypeError);
  await assert.rejects(client.inviteMember(session, { subject: 'oidc|user', role: 'viewer', tenant_id: 'not-accepted' }), TypeError);
  await assert.rejects(client.updateMember(session, 'oidc|user', { action: 'promote' }), TypeError);
  await assert.rejects(client.updateMember(session, 'oidc|user', { action: 'suspend', role: 'viewer' }), TypeError);
  await assert.rejects(client.updateMember(session, 'oidc|user', { action: 'revoke', tenant_id: 'not-accepted' }), TypeError);
  assert.equal(calls, 0);
});

test('membership client rejects unexpected response fields and sanitizes service errors', async () => {
  const invalidClient = createMembershipClient('https://api.aegis.invalid', async () => (
    new Response(JSON.stringify([{ ...member, tenant_id: 'must-not-be-accepted' }]), { status: 200 })
  ));
  await assert.rejects(
    invalidClient.listMembers(session),
    (error) => error instanceof MembershipApiError && error.code === 'invalid_response',
  );

  const failedClient = createMembershipClient('https://api.aegis.invalid', async () => (
    new Response('database-password-must-not-appear', { status: 503 })
  ));
  await assert.rejects(
    failedClient.listMembers(session),
    (error) => {
      assert.ok(error instanceof MembershipApiError);
      assert.equal(error.status, 503);
      assert.doesNotMatch(error.message, /database-password/);
      return true;
    },
  );
});
