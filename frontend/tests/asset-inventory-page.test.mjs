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
    optimizeDeps: { noDiscovery: true, include: [] },
    appType: 'custom',
  });

  ({ AssetInventoryPage } = await vite.ssrLoadModule('/src/pages/AssetInventoryPage.tsx'));
});

after(async () => {
  await vite?.close();
});

test('asset inventory requires a trusted session and does not render fabricated records', () => {
  const markup = renderToStaticMarkup(React.createElement(AssetInventoryPage));

  assert.match(markup, /Connect your organization account/);
  assert.match(markup, /trusted sign-in and server-side membership check/);
  assert.doesNotMatch(markup, /Production API|d8a3e9c4|f5d4c3b2/);
  assert.doesNotMatch(markup, /Register asset/);
});
