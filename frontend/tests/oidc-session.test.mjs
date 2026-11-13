import assert from 'node:assert/strict';
import { webcrypto } from 'node:crypto';
import { after, before, test } from 'node:test';
import react from '@vitejs/plugin-react';
import { createServer } from 'vite';

let vite;
let createOidcSessionAdapter;
let readOidcClientConfig;
let OidcAuthenticationError;

before(async () => {
  vite = await createServer({
    configFile: false,
    plugins: [react()],
    server: { middlewareMode: true, hmr: false },
    optimizeDeps: { noDiscovery: true, include: [] },
    appType: 'custom',
  });
  ({ createOidcSessionAdapter, readOidcClientConfig, OidcAuthenticationError } =
    await vite.ssrLoadModule('/src/auth/oidc.ts'));
});

after(async () => {
  await vite?.close();
});

const issuer = 'https://identity.example.test';
const redirectUri = 'https://portal.example.test/auth/callback';
const clientId = 'aegis-public-client';
const discoveryUrl = `${issuer}/.well-known/openid-configuration`;
const tokenUrl = `${issuer}/oauth/token`;
const jwksUrl = `${issuer}/.well-known/jwks.json`;

function encodeBase64Url(value) {
  return Buffer.from(value).toString('base64url');
}

async function signIdToken(privateKey, claims, kid = 'test-key') {
  const header = encodeBase64Url(JSON.stringify({ alg: 'RS256', typ: 'JWT', kid }));
  const payload = encodeBase64Url(JSON.stringify(claims));
  const input = `${header}.${payload}`;
  const signature = await webcrypto.subtle.sign(
    { name: 'RSASSA-PKCS1-v1_5' },
    privateKey,
    new TextEncoder().encode(input),
  );
  return `${input}.${Buffer.from(signature).toString('base64url')}`;
}

class MemoryStorage {
  values = new Map();
  getItem(key) { return this.values.get(key) ?? null; }
  setItem(key, value) { this.values.set(key, value); }
  removeItem(key) { this.values.delete(key); }
}

let keyPair;
let publicJwk;
let now;

before(async () => {
  keyPair = await webcrypto.subtle.generateKey(
    {
      name: 'RSASSA-PKCS1-v1_5',
      modulusLength: 2048,
      publicExponent: new Uint8Array([1, 0, 1]),
      hash: 'SHA-256',
    },
    true,
    ['sign', 'verify'],
  );
  publicJwk = {
    ...(await webcrypto.subtle.exportKey('jwk', keyPair.publicKey)),
    kid: 'test-key',
    use: 'sig',
    alg: 'RS256',
    key_ops: ['verify'],
  };
});

function createHarness({ claims = {}, tokenOverrides = {}, discoveryOverrides = {}, clockSkewSeconds = 0, fetchOverride } = {}) {
  now = Date.parse('2026-11-13T12:00:00.000Z');
  const storage = new MemoryStorage();
  const location = {
    origin: 'https://portal.example.test',
    href: redirectUri,
    assigned: null,
    assign(url) { this.assigned = String(url); },
  };
  const history = {
    replaced: null,
    replaceState(_state, _title, url) { this.replaced = String(url); },
  };
  let tokenRequests = 0;
  let tokenRequestBody = null;
  let expectedNonce = null;
  const discovery = {
    issuer,
    authorization_endpoint: `${issuer}/oauth/authorize`,
    token_endpoint: tokenUrl,
    jwks_uri: jwksUrl,
    response_types_supported: ['code'],
    code_challenge_methods_supported: ['S256'],
    id_token_signing_alg_values_supported: ['RS256'],
    ...discoveryOverrides,
  };
  const fetchImplementation = fetchOverride ?? (async (url, init = {}) => {
    if (String(url) === discoveryUrl) {
      return new Response(JSON.stringify(discovery), { status: 200 });
    }
    if (String(url) === jwksUrl) {
      return new Response(JSON.stringify({ keys: [publicJwk] }), { status: 200 });
    }
    if (String(url) === tokenUrl) {
      tokenRequests += 1;
      tokenRequestBody = new URLSearchParams(init.body);
      const transaction = JSON.parse(storage.getItem('aegis.oidc.transaction.v1') ?? 'null');
      const nonce = expectedNonce ?? transaction?.nonce ?? claims.nonce;
      const idTokenClaims = {
        iss: issuer,
        aud: clientId,
        sub: 'oidc|sir-prince-test-user',
        exp: Math.floor(now / 1000) + 600,
        iat: Math.floor(now / 1000),
        nonce,
        ...claims,
      };
      const idToken = tokenOverrides.id_token ?? await signIdToken(keyPair.privateKey, idTokenClaims);
      return new Response(JSON.stringify({
        access_token: 'short-lived-test-access-token',
        token_type: 'Bearer',
        expires_in: 3600,
        id_token: idToken,
        ...tokenOverrides,
      }), { status: 200 });
    }
    throw new Error(`Unexpected URL: ${url}`);
  });
  const adapter = createOidcSessionAdapter({ issuer, clientId, redirectUri, clockSkewSeconds }, {
    fetch: fetchImplementation,
    crypto: webcrypto,
    storage,
    location,
    history,
    now: () => now,
  });
  return {
    adapter,
    storage,
    location,
    history,
    get tokenRequests() { return tokenRequests; },
    get tokenRequestBody() { return tokenRequestBody; },
    setExpectedNonce(value) { expectedNonce = value; },
    setTokenOverride(name, value) { tokenOverrides[name] = value; },
    advance(ms) { now += ms; },
  };
}

test('OIDC environment config stays disabled until all public client settings exist', () => {
  assert.equal(readOidcClientConfig({}), null);
  assert.throws(
    () => readOidcClientConfig({ VITE_AEGIS_OIDC_ISSUER: issuer }),
    (error) => error instanceof OidcAuthenticationError && error.code === 'invalid_configuration',
  );
  assert.throws(
    () => readOidcClientConfig({
      VITE_AEGIS_OIDC_ISSUER: issuer,
      VITE_AEGIS_OIDC_CLIENT_ID: clientId,
      VITE_AEGIS_OIDC_REDIRECT_URI: redirectUri,
      VITE_AEGIS_OIDC_CLIENT_SECRET: 'must-never-be-used',
    }),
    (error) => error instanceof OidcAuthenticationError && error.code === 'invalid_configuration',
  );
});

test('sign-in uses Authorization Code + PKCE S256 and stores only a short-lived transaction', async () => {
  const harness = createHarness();
  await harness.adapter.signIn({ returnTo: '/assets?filter=endpoint' });
  const authorizationUrl = new URL(harness.location.assigned);
  const transaction = JSON.parse(harness.storage.getItem('aegis.oidc.transaction.v1'));
  const expectedChallenge = Buffer.from(await webcrypto.subtle.digest(
    'SHA-256', new TextEncoder().encode(transaction.codeVerifier),
  )).toString('base64url');

  assert.equal(authorizationUrl.searchParams.get('response_type'), 'code');
  assert.equal(authorizationUrl.searchParams.get('client_id'), clientId);
  assert.equal(authorizationUrl.searchParams.get('redirect_uri'), redirectUri);
  assert.equal(authorizationUrl.searchParams.get('code_challenge_method'), 'S256');
  assert.equal(authorizationUrl.searchParams.get('code_challenge'), expectedChallenge);
  assert.equal(authorizationUrl.searchParams.get('state'), transaction.state);
  assert.equal(authorizationUrl.searchParams.get('nonce'), transaction.nonce);
  assert.equal(authorizationUrl.searchParams.has('code_verifier'), false);
  assert.equal(authorizationUrl.searchParams.has('client_secret'), false);
  assert.equal(harness.adapter.getSession(), null);
});

test('callback validates the signed ID token, consumes state, scrubs the URL and keeps access token in memory', async () => {
  const harness = createHarness();
  await harness.adapter.signIn({ returnTo: '/members' });
  const transaction = JSON.parse(harness.storage.getItem('aegis.oidc.transaction.v1'));
  harness.setExpectedNonce(transaction.nonce);
  const result = await harness.adapter.completeSignIn(
    `${redirectUri}?code=authorization-code&state=${encodeURIComponent(transaction.state)}`,
  );

  assert.equal(result.session.subject, 'oidc|sir-prince-test-user');
  assert.equal(result.session.accessToken, 'short-lived-test-access-token');
  assert.equal(result.returnTo, '/members');
  assert.equal(harness.adapter.getSession().accessToken, result.session.accessToken);
  assert.equal(harness.storage.getItem('aegis.oidc.transaction.v1'), null);
  assert.equal(harness.history.replaced, redirectUri);
  assert.equal(harness.tokenRequestBody.get('code_verifier'), transaction.codeVerifier);
  assert.equal(harness.tokenRequestBody.has('client_secret'), false);
});

test('callback rejects missing or mismatched state before exchanging the code', async () => {
  const harness = createHarness();
  await harness.adapter.signIn();
  await assert.rejects(
    harness.adapter.completeSignIn(`${redirectUri}?code=authorization-code&state=wrong-state`),
    (error) => error instanceof OidcAuthenticationError && error.code === 'invalid_state',
  );
  assert.equal(harness.tokenRequests, 0);
  assert.equal(harness.adapter.getSession(), null);
});

test('callback rejects a signed ID token with the wrong nonce, issuer or audience', async (t) => {
  for (const [name, claims] of [
    ['nonce', { nonce: 'wrong-nonce' }],
    ['issuer', { iss: 'https://attacker.example.test' }],
    ['audience', { aud: 'another-client' }],
  ]) {
    await t.test(name, async () => {
      const harness = createHarness({ claims });
      await harness.adapter.signIn();
      const transaction = JSON.parse(harness.storage.getItem('aegis.oidc.transaction.v1'));
      harness.setExpectedNonce(transaction.nonce);
      await assert.rejects(
        harness.adapter.completeSignIn(`${redirectUri}?code=authorization-code&state=${transaction.state}`),
        (error) => error instanceof OidcAuthenticationError && error.code === 'verification_failed',
      );
      assert.equal(harness.adapter.getSession(), null);
    });
  }
});

test('callback rejects an invalid signature and expired ID token', async (t) => {
  await t.test('invalid signature', async () => {
    const harness = createHarness();
    await harness.adapter.signIn();
    const transaction = JSON.parse(harness.storage.getItem('aegis.oidc.transaction.v1'));
    harness.setExpectedNonce(transaction.nonce);
    const rogueKeyPair = await webcrypto.subtle.generateKey(
      {
        name: 'RSASSA-PKCS1-v1_5',
        modulusLength: 2048,
        publicExponent: new Uint8Array([1, 0, 1]),
        hash: 'SHA-256',
      },
      true,
      ['sign', 'verify'],
    );
    const rogueToken = await signIdToken(rogueKeyPair.privateKey, {
      iss: issuer,
      aud: clientId,
      sub: 'attacker-subject',
      exp: Math.floor(now / 1000) + 600,
      iat: Math.floor(now / 1000),
      nonce: transaction.nonce,
    });
    harness.setTokenOverride('id_token', rogueToken);
    await assert.rejects(
      harness.adapter.completeSignIn(`${redirectUri}?code=authorization-code&state=${transaction.state}`),
      (error) => error instanceof OidcAuthenticationError && error.code === 'verification_failed',
    );
  });
  await t.test('expired ID token', async () => {
    const harness = createHarness({ claims: { exp: Math.floor(Date.parse('2026-11-13T12:00:00.000Z') / 1000) - 120 } });
    await harness.adapter.signIn();
    const transaction = JSON.parse(harness.storage.getItem('aegis.oidc.transaction.v1'));
    harness.setExpectedNonce(transaction.nonce);
    await assert.rejects(
      harness.adapter.completeSignIn(`${redirectUri}?code=authorization-code&state=${transaction.state}`),
      (error) => error instanceof OidcAuthenticationError && error.code === 'verification_failed',
    );
  });
});


test('ID token multiple audiences require the authorized party to match the client', async (t) => {
  await t.test('matching azp is accepted', async () => {
    const harness = createHarness({ claims: { aud: [clientId, 'aegis-api'], azp: clientId } });
    await harness.adapter.signIn();
    const transaction = JSON.parse(harness.storage.getItem('aegis.oidc.transaction.v1'));
    harness.setExpectedNonce(transaction.nonce);
    const result = await harness.adapter.completeSignIn(`${redirectUri}?code=authorization-code&state=${transaction.state}`);
    assert.equal(result.session.subject, 'oidc|sir-prince-test-user');
  });
  await t.test('missing azp is rejected', async () => {
    const harness = createHarness({ claims: { aud: [clientId, 'aegis-api'] } });
    await harness.adapter.signIn();
    const transaction = JSON.parse(harness.storage.getItem('aegis.oidc.transaction.v1'));
    harness.setExpectedNonce(transaction.nonce);
    await assert.rejects(
      harness.adapter.completeSignIn(`${redirectUri}?code=authorization-code&state=${transaction.state}`),
      (error) => error instanceof OidcAuthenticationError && error.code === 'verification_failed',
    );
  });
});

test('callback rejects expired transactions and malformed access tokens', async (t) => {
  await t.test('expired transaction', async () => {
    const harness = createHarness();
    await harness.adapter.signIn();
    const transaction = JSON.parse(harness.storage.getItem('aegis.oidc.transaction.v1'));
    harness.advance(11 * 60 * 1000);
    await assert.rejects(
      harness.adapter.completeSignIn(`${redirectUri}?code=authorization-code&state=${transaction.state}`),
      (error) => error instanceof OidcAuthenticationError && error.code === 'expired_transaction',
    );
    assert.equal(harness.tokenRequests, 0);
  });
  await t.test('control characters in access token', async () => {
    const harness = createHarness({ tokenOverrides: { access_token: 'token\r\nInjected: yes' } });
    await harness.adapter.signIn();
    const transaction = JSON.parse(harness.storage.getItem('aegis.oidc.transaction.v1'));
    harness.setExpectedNonce(transaction.nonce);
    await assert.rejects(
      harness.adapter.completeSignIn(`${redirectUri}?code=authorization-code&state=${transaction.state}`),
      (error) => error instanceof OidcAuthenticationError && error.code === 'invalid_response',
    );
    assert.equal(harness.adapter.getSession(), null);
  });
});

test('OIDC discovery must advertise authorization code, PKCE S256 and RS256', async () => {
  const harness = createHarness({ discoveryOverrides: { code_challenge_methods_supported: ['plain'] } });
  await assert.rejects(
    harness.adapter.signIn(),
    (error) => error instanceof OidcAuthenticationError && error.code === 'invalid_response',
  );
  assert.equal(harness.location.assigned, null);
});

test('expired in-memory sessions are discarded and sign-out clears the local session', async () => {
  const harness = createHarness({ clockSkewSeconds: 0 });
  await harness.adapter.signIn();
  const transaction = JSON.parse(harness.storage.getItem('aegis.oidc.transaction.v1'));
  harness.setExpectedNonce(transaction.nonce);
  await harness.adapter.completeSignIn(`${redirectUri}?code=authorization-code&state=${transaction.state}`);
  assert.ok(harness.adapter.getSession());
  harness.advance(3600 * 1000 + 1);
  assert.equal(harness.adapter.getSession(), null);

  await harness.adapter.signIn();
  assert.ok(harness.storage.getItem('aegis.oidc.transaction.v1'));
  harness.adapter.signOut();
  assert.equal(harness.adapter.getSession(), null);
  assert.equal(harness.storage.getItem('aegis.oidc.transaction.v1'), null);
});

test('unsafe return paths and callback origins are rejected', async () => {
  const harness = createHarness();
  await assert.rejects(harness.adapter.signIn({ returnTo: '//attacker.example.test' }), OidcAuthenticationError);
  await harness.adapter.signIn();
  const transaction = JSON.parse(harness.storage.getItem('aegis.oidc.transaction.v1'));
  await assert.rejects(
    harness.adapter.completeSignIn(`https://attacker.example.test/auth/callback?code=x&state=${transaction.state}`),
    (error) => error instanceof OidcAuthenticationError && error.code === 'invalid_state',
  );
});
