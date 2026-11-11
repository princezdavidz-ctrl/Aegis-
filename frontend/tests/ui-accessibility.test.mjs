import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import React from 'react';
import { after, before, test } from 'node:test';
import { renderToStaticMarkup } from 'react-dom/server';
import react from '@vitejs/plugin-react';
import { createServer } from 'vite';

const expectedLabels = [
  'Overview',
  'Organization',
  'Investigations',
  'AI agents',
  'Integrations',
  'Memory',
  'Audit log',
];

let vite;
let App;
let Sidebar;
let OrganizationPage;
let platformReadiness;

before(async () => {
  vite = await createServer({
    configFile: false,
    plugins: [react()],
    server: { middlewareMode: true, hmr: false },
    optimizeDeps: { noDiscovery: true, include: [] },
    appType: 'custom',
  });

  ({ default: App } = await vite.ssrLoadModule('/src/App.tsx'));
  ({ Sidebar } = await vite.ssrLoadModule('/src/components/Sidebar.tsx'));
  ({ OrganizationPage } = await vite.ssrLoadModule('/src/pages/OrganizationPage.tsx'));
  ({ platformReadiness } = await vite.ssrLoadModule('/src/data/platformReadiness.ts'));
});

after(async () => {
  await vite?.close();
});

function findNavigation(markup, label) {
  const openingTag = '<nav aria-label="' + label + '"';
  const start = markup.indexOf(openingTag);

  assert.notEqual(start, -1, 'Expected a navigation landmark named "' + label + '"');

  const end = markup.indexOf('</nav>', start);
  assert.notEqual(end, -1, 'Expected the "' + label + '" navigation landmark to close');

  return markup.slice(start, end + '</nav>'.length);
}

function getButtons(markup) {
  return [...markup.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/g)].map((match) => ({
    attributes: match[1],
    label: match[2].replace(/<[^>]*>/g, '').trim(),
  }));
}

test('dashboard exposes separately named desktop and mobile navigation landmarks', () => {
  const markup = renderToStaticMarkup(React.createElement(App));

  const primary = findNavigation(markup, 'Primary navigation');
  const mobile = findNavigation(markup, 'Mobile navigation');

  for (const navigation of [primary, mobile]) {
    const buttons = getButtons(navigation);

    assert.deepEqual(buttons.map(({ label }) => label), expectedLabels);
    assert.ok(
      buttons.every(({ attributes }) => /\btype="button"/.test(attributes)),
      'Navigation controls must be non-submitting native buttons',
    );
    assert.equal(
      buttons.filter(({ attributes }) => /\baria-current="page"/.test(attributes)).length,
      1,
      'Each navigation landmark must expose exactly one current page',
    );
    assert.match(
      buttons[0].attributes,
      /\baria-current="page"/,
      'Overview is the initial selected page',
    );
  }
});

test('Sidebar exposes the selected section through aria-current', () => {
  const markup = renderToStaticMarkup(
    React.createElement(Sidebar, {
      activeSection: 'organization',
      onNavigate: () => {},
    }),
  );
  const navigation = findNavigation(markup, 'Primary navigation');
  const buttons = getButtons(navigation);

  assert.equal(buttons.length, expectedLabels.length);
  assert.equal(
    buttons.filter(({ attributes }) => /\baria-current="page"/.test(attributes)).length,
    1,
  );
  assert.match(
    buttons.find(({ label }) => label === 'Organization').attributes,
    /\baria-current="page"/,
  );
  assert.doesNotMatch(
    buttons.find(({ label }) => label === 'Overview').attributes,
    /\baria-current="page"/,
  );
});

test('navigation controls retain a visible keyboard focus indicator', async () => {
  const stylesheet = await readFile(new URL('../src/index.css', import.meta.url), 'utf8');

  assert.match(
    stylesheet,
    /button:focus-visible\s*\{[^}]*outline:\s*2px[^}]*outline-offset:\s*3px/s,
    'Keyboard focus must be visibly distinguishable',
  );
});

test('organization page explains the missing verified session without showing sample data', () => {
  const markup = renderToStaticMarkup(React.createElement(OrganizationPage));

  assert.match(markup, /Connect your organization account/);
  assert.match(markup, /trusted sign-in and server-side membership check/);
  assert.match(markup, /no sample organization data is displayed/);
  assert.doesNotMatch(markup, /Example Corp|Acme Security|example\.com/);
});

test('overview distinguishes implemented code, CI evidence and unconfigured services', () => {
  const markup = renderToStaticMarkup(React.createElement(App));

  assert.match(markup, /Code present/);
  assert.match(markup, /CI verified/);
  assert.match(markup, /Provider unconfigured/);
  assert.match(markup, /Not implemented/);
  assert.match(markup, /not live service health/);
  assert.doesNotMatch(markup, />Pending<\/span>/);
});

test('platform readiness labels match the implementation catalog', () => {
  assert.deepEqual(
    platformReadiness.map(({ status }) => status),
    ['Code present', 'CI verified', 'Provider unconfigured', 'Not implemented'],
  );
});
