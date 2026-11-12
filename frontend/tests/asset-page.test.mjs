import assert from 'node:assert/strict';
import React from 'react';
import { after, before, test } from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import react from '@vitejs/plugin-react';
import { createServer } from 'vite';

let vite;
let AssetInventoryPage;

before(async () => {
  vite = await createServer({
    configFile: false,
    plugins: [react()],
    server: { middlewareMode: true, hmr: false },
    optimizeDeps: { noDiscovery: true },
    appType: 'custom',
  });
  ({ AssetInventoryPage } = await vite.ssrLoadModule('/src/pages/AssetInventoryPage.tsx'));
});

after(async () => {
  await vite?.close();
});

test('asset inventory requires a verified session and never renders sample records', () => {
  const markup = renderToStaticMarkup(
    React.createElement(AssetInventoryPage, { apiBaseUrl: 'https://api.example.test' }),
  );
  assert.match(markup, /Connect your organization account/);
  assert.match(markup, /trusted sign-in and a server-side membership check/);
  assert.doesNotMatch(markup, /Production API|svc-api-001/);
});

test('asset inventory reports missing API configuration after a session is supplied', () => {
  const markup = renderToStaticMarkup(
    React.createElement(AssetInventoryPage, {
      session: { accessToken: 'ephemeral-test-token', tenantSlug: 'acme-security' },
    }),
  );
  assert.match(markup, /API connection is not configured/);
  assert.match(markup, /VITE_AEGIS_API_BASE_URL/);
});
