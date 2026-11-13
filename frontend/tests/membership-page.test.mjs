import assert from 'node:assert/strict';
import React from 'react';
import { after, before, test } from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import react from '@vitejs/plugin-react';
import { createServer } from 'vite';

let vite;
let MembershipPage;

before(async () => {
  vite = await createServer({
    configFile: false,
    plugins: [react()],
    server: { middlewareMode: true, hmr: false },
    optimizeDeps: { noDiscovery: true, include: [] },
    appType: 'custom',
  });

  ({ MembershipPage } = await vite.ssrLoadModule('/src/pages/MembershipPage.tsx'));
});

after(async () => {
  await vite?.close();
});

test('member management requires a trusted session and renders no fabricated identities', () => {
  const markup = renderToStaticMarkup(React.createElement(MembershipPage));

  assert.match(markup, /Connect your organization account/);
  assert.match(markup, /trusted sign-in and server-side membership resolution/);
  assert.doesNotMatch(markup, /oidc\|existing-user|Example User|Acme Corp/);
  assert.doesNotMatch(markup, /Create invitation|Revoke/);
});

test('member management denies non-administrators before exposing management controls', () => {
  const markup = renderToStaticMarkup(React.createElement(MembershipPage, {
    session: {
      accessToken: 'test-token-not-a-credential',
      tenantSlug: 'northstar-security',
      membershipRole: 'analyst',
      subject: 'oidc|analyst',
    },
  }));

  assert.match(markup, /Tenant administrator access required/);
  assert.doesNotMatch(markup, /Create invitation|Revoke|Suspend/);
});
