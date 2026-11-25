import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const api = await readFile(new URL('../src/api/endpoints.ts', import.meta.url), 'utf8');
const page = await readFile(new URL('../src/pages/EndpointFleetPage.tsx', import.meta.url), 'utf8');
const app = await readFile(new URL('../src/App.tsx', import.meta.url), 'utf8');

test('endpoint client enforces HTTPS, tenant headers and bounded fleet results', () => {
  assert.match(api, /https:/);
  assert.match(api, /X-AEGIS-Tenant/);
  assert.match(api, /credentials: 'omit'/);
  assert.match(api, /limit < 1 \|\| limit > 500/);
  assert.match(api, /isDevice/);
});

test('endpoint client rejects unknown response fields and invalid device IDs', () => {
  assert.match(api, /Object\.keys\(value\).*allowed/);
  assert.match(api, /UUID_PATTERN\.test\(deviceId\)/);
  assert.match(api, /new EndpointApiError\(200, 'invalid_response'\)/);
});

test('fleet page gates revocation by verified tenant role and confirms action', () => {
  assert.match(page, /tenant_admin/);
  assert.match(page, /security_manager/);
  assert.match(page, /window\.confirm/);
  assert.match(page, /device\.status !== 'active'/);
});

test('app mounts fleet view only for the authenticated tenant session', () => {
  assert.match(app, /EndpointFleetPage/);
  assert.match(app, /active === 'agents'/);
  assert.match(app, /auth\.tenantSession/);
});

test('enrollment invitation API is bounded, platform-bound and validates one-time token response', () => {
  assert.match(api, /createInvitation\(session: TenantSession, platform: EndpointPlatform/);
  assert.match(api, /ttlMinutes < 5 \|\| ttlMinutes > 1440/);
  assert.match(api, /\/api\/v1\/endpoints\/invitations/);
  assert.match(api, /enrollment_token/);
  assert.match(page, /One-time enrollment token/);
  assert.match(page, /window\.navigator\.clipboard\.writeText/);
});
