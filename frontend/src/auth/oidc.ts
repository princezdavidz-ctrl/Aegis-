/**
 * Provider-neutral browser OIDC Authorization Code + PKCE client.
 * Access tokens and ID tokens are kept in memory only. The short-lived PKCE
 * transaction is held in sessionStorage so the redirect can complete safely.
 * The API remains responsible for independently verifying access-token claims.
 */

export interface OidcClientConfig {
  issuer: string;
  clientId: string;
  redirectUri: string;
  scopes?: readonly string[];
  clockSkewSeconds?: number;
  allowLoopbackHttp?: boolean;
}

export interface OidcSession {
  readonly accessToken: string;
  readonly subject: string;
  readonly expiresAt: number;
}

export interface OidcSignInOptions {
  returnTo?: string;
  prompt?: 'none' | 'login' | 'consent' | 'select_account';
}

export interface OidcSignInResult {
  readonly session: OidcSession;
  /** A validated same-origin path; the caller decides how to navigate. */
  readonly returnTo: string;
}

export interface OidcBrowserDependencies {
  fetch: typeof fetch;
  crypto: Crypto;
  storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;
  location: Pick<Location, 'origin' | 'href' | 'assign'>;
  history: Pick<History, 'replaceState'>;
  now: () => number;
}

type JsonRecord = Record<string, unknown>;

interface OidcDiscovery {
  issuer: string;
  authorization_endpoint: string;
  token_endpoint: string;
  jwks_uri: string;
  response_types_supported: string[];
  code_challenge_methods_supported: string[];
  id_token_signing_alg_values_supported: string[];
}

type SigningJwk = JsonWebKey & { kid?: string; use?: string; alg?: string };

interface AuthTransaction {
  state: string;
  nonce: string;
  codeVerifier: string;
  createdAt: number;
  returnTo: string;
}

const TRANSACTION_KEY = 'aegis.oidc.transaction.v1';
const TRANSACTION_TTL_MS = 10 * 60 * 1000;
const MAX_ACCESS_TOKEN_LENGTH = 8192;
const MAX_ID_TOKEN_LENGTH = 16384;
const MAX_JWKS_KEYS = 50;
const JWKS_CACHE_MS = 5 * 60 * 1000;
const DEFAULT_SCOPES = ['openid', 'profile', 'email'] as const;
const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]']);

export type OidcAuthenticationErrorCode =
  | 'not_configured'
  | 'invalid_configuration'
  | 'invalid_response'
  | 'invalid_state'
  | 'expired_transaction'
  | 'provider_error'
  | 'verification_failed'
  | 'provider_unavailable';

export class OidcAuthenticationError extends Error {
  readonly code: OidcAuthenticationErrorCode;

  constructor(code: OidcAuthenticationErrorCode) {
    const messages: Record<OidcAuthenticationErrorCode, string> = {
      not_configured: 'AEGIS sign-in is not configured.',
      invalid_configuration: 'AEGIS sign-in configuration is invalid.',
      invalid_response: 'The identity provider returned an invalid response.',
      invalid_state: 'The sign-in response could not be verified. Start sign-in again.',
      expired_transaction: 'The sign-in request expired. Start sign-in again.',
      provider_error: 'The identity provider could not complete sign-in.',
      verification_failed: 'The identity provider response could not be verified.',
      provider_unavailable: 'The identity provider is temporarily unavailable.',
    };
    super(messages[code]);
    this.name = 'OidcAuthenticationError';
    this.code = code;
  }
}

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function trustedUrl(value: string, allowLoopbackHttp: boolean): URL {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new OidcAuthenticationError('invalid_configuration');
  }
  const loopbackHttp = url.protocol === 'http:' && LOOPBACK_HOSTS.has(url.hostname);
  if (
    (url.protocol !== 'https:' && !(allowLoopbackHttp && loopbackHttp)) ||
    url.username || url.password || url.search || url.hash
  ) {
    throw new OidcAuthenticationError('invalid_configuration');
  }
  return url;
}

function validateConfig(config: OidcClientConfig, browserOrigin: string): Required<OidcClientConfig> {
  const allowLoopbackHttp = config.allowLoopbackHttp === true;
  trustedUrl(config.issuer, allowLoopbackHttp);
  // OIDC issuer comparison is exact; preserve its configured trailing-slash form.
  if (config.issuer !== config.issuer.trim() || config.redirectUri !== config.redirectUri.trim()) {
    throw new OidcAuthenticationError('invalid_configuration');
  }
  const issuer = config.issuer;
  const redirect = trustedUrl(config.redirectUri, allowLoopbackHttp);
  if (redirect.origin !== browserOrigin || redirect.origin !== new URL(browserOrigin).origin) {
    throw new OidcAuthenticationError('invalid_configuration');
  }
  if (
    !config.clientId || config.clientId !== config.clientId.trim() || config.clientId.length > 255 ||
    /[\u0000-\u0020]/.test(config.clientId)
  ) {
    throw new OidcAuthenticationError('invalid_configuration');
  }
  const scopes = [...(config.scopes ?? DEFAULT_SCOPES)];
  if (
    scopes.length === 0 || scopes.length > 10 || !scopes.includes('openid') ||
    new Set(scopes).size !== scopes.length ||
    scopes.some((scope) => !/^[A-Za-z0-9:_./-]{1,64}$/.test(scope))
  ) {
    throw new OidcAuthenticationError('invalid_configuration');
  }
  const clockSkewSeconds = config.clockSkewSeconds ?? 60;
  if (!Number.isInteger(clockSkewSeconds) || clockSkewSeconds < 0 || clockSkewSeconds > 300) {
    throw new OidcAuthenticationError('invalid_configuration');
  }
  return {
    issuer,
    clientId: config.clientId,
    redirectUri: config.redirectUri,
    scopes,
    clockSkewSeconds,
    allowLoopbackHttp,
  };
}

function browserDependencies(): OidcBrowserDependencies {
  if (typeof window === 'undefined') {
    throw new OidcAuthenticationError('not_configured');
  }
  return {
    fetch: window.fetch.bind(window),
    crypto: window.crypto,
    storage: window.sessionStorage,
    location: window.location,
    history: window.history,
    now: () => Date.now(),
  };
}

function base64UrlEncode(bytes: Uint8Array): string {
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  const buffer = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(buffer).set(bytes);
  return buffer;
}

function base64UrlDecode(value: string): Uint8Array {
  if (!/^[A-Za-z0-9_-]+$/.test(value) || value.length % 4 === 1) {
    throw new OidcAuthenticationError('verification_failed');
  }
  const padded = value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4);
  let binary: string;
  try {
    binary = atob(padded);
  } catch {
    throw new OidcAuthenticationError('verification_failed');
  }
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function decodeJsonPart(value: string): JsonRecord {
  try {
    const decoded = new TextDecoder('utf-8', { fatal: true }).decode(base64UrlDecode(value));
    const parsed: unknown = JSON.parse(decoded);
    if (!isRecord(parsed)) throw new Error('not an object');
    return parsed;
  } catch {
    throw new OidcAuthenticationError('verification_failed');
  }
}

function constantTimeEqual(left: string, right: string): boolean {
  if (left.length !== right.length) return false;
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return difference === 0;
}

function normalizeReturnTo(value: string | undefined, origin: string): string {
  const candidate = value ?? '/';
  if (!candidate.startsWith('/') || candidate.startsWith('//') || candidate.includes('\\') || /[\u0000-\u001f]/.test(candidate)) {
    throw new OidcAuthenticationError('invalid_configuration');
  }
  const url = new URL(candidate, origin);
  if (url.origin !== origin) throw new OidcAuthenticationError('invalid_configuration');
  return `${url.pathname}${url.search}${url.hash}`;
}

function readTransaction(storage: OidcBrowserDependencies['storage']): AuthTransaction | null {
  let raw: string | null;
  try {
    raw = storage.getItem(TRANSACTION_KEY);
  } catch {
    throw new OidcAuthenticationError('provider_unavailable');
  }
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (
      !isRecord(value) || typeof value.state !== 'string' || typeof value.nonce !== 'string' ||
      typeof value.codeVerifier !== 'string' || typeof value.createdAt !== 'number' ||
      typeof value.returnTo !== 'string'
    ) return null;
    if (
      value.state.length !== 43 || value.nonce.length !== 43 ||
      !/^[A-Za-z0-9_-]{43,128}$/.test(value.codeVerifier) ||
      !Number.isFinite(value.createdAt)
    ) return null;
    return value as unknown as AuthTransaction;
  } catch {
    return null;
  }
}

function clearTransaction(storage: OidcBrowserDependencies['storage']): void {
  try {
    storage.removeItem(TRANSACTION_KEY);
  } catch {
    throw new OidcAuthenticationError('provider_unavailable');
  }
}

async function parseJsonResponse(response: Response): Promise<JsonRecord> {
  if (!response.ok) throw new OidcAuthenticationError('provider_unavailable');
  try {
    const payload: unknown = await response.json();
    if (!isRecord(payload)) throw new Error('not an object');
    return payload;
  } catch {
    throw new OidcAuthenticationError('invalid_response');
  }
}

function isRsaSigningKey(value: SigningJwk): boolean {
  try {
    if (
      typeof value.kid !== 'string' || value.kid.length === 0 || value.kid.length > 256 ||
      /[\u0000-\u001f\u007f]/.test(value.kid) ||
      typeof value.n !== 'string' || typeof value.e !== 'string' ||
      value.d !== undefined || value.p !== undefined || value.q !== undefined ||
      value.dp !== undefined || value.dq !== undefined || value.qi !== undefined || value.oth !== undefined ||
      (value.use !== undefined && value.use !== 'sig') ||
      (value.alg !== undefined && value.alg !== 'RS256') ||
      (value.key_ops !== undefined && (!Array.isArray(value.key_ops) || !value.key_ops.includes('verify')))
    ) return false;
    const modulus = base64UrlDecode(value.n);
    const exponent = base64UrlDecode(value.e);
    const exponentValue = exponent.reduce((total, byte) => total * 256 + byte, 0);
    return modulus.length >= 256 && modulus.length <= 1024 && exponentValue >= 3 && exponentValue % 2 === 1;
  } catch {
    return false;
  }
}

function validateEndpoint(value: unknown, allowLoopbackHttp: boolean): string {
  if (typeof value !== 'string') throw new OidcAuthenticationError('invalid_response');
  try {
    return trustedUrl(value, allowLoopbackHttp).href;
  } catch {
    throw new OidcAuthenticationError('invalid_response');
  }
}

export function readOidcClientConfig(
  environment: Record<string, string | undefined>,
  allowLoopbackHttp = false,
): OidcClientConfig | null {
  if (environment.VITE_AEGIS_OIDC_CLIENT_SECRET?.trim()) {
    throw new OidcAuthenticationError('invalid_configuration');
  }
  const issuer = environment.VITE_AEGIS_OIDC_ISSUER?.trim() ?? '';
  const clientId = environment.VITE_AEGIS_OIDC_CLIENT_ID?.trim() ?? '';
  const redirectUri = environment.VITE_AEGIS_OIDC_REDIRECT_URI?.trim() ?? '';
  if (![issuer, clientId, redirectUri].some(Boolean)) return null;
  if (![issuer, clientId, redirectUri].every(Boolean)) {
    throw new OidcAuthenticationError('invalid_configuration');
  }
  return Object.freeze({ issuer, clientId, redirectUri, allowLoopbackHttp });
}

export function createOidcSessionAdapter(
  inputConfig: OidcClientConfig,
  injectedDependencies?: OidcBrowserDependencies,
) {
  const dependencies = injectedDependencies ?? browserDependencies();
  const config = validateConfig(inputConfig, dependencies.location.origin);
  let session: OidcSession | null = null;
  let metadata: OidcDiscovery | null = null;
  let metadataExpiresAt = 0;
  let jwks: SigningJwk[] | null = null;
  let lastUnknownKidRefreshAt = 0;
  let jwksExpiresAt = 0;

  async function requestJson(url: string, init?: RequestInit): Promise<JsonRecord> {
    let response: Response;
    try {
      response = await dependencies.fetch(url, {
        ...init,
        cache: 'no-store',
        credentials: 'omit',
        redirect: 'error',
        referrerPolicy: 'no-referrer',
      });
    } catch {
      throw new OidcAuthenticationError('provider_unavailable');
    }
    return parseJsonResponse(response);
  }

  async function getMetadata(force = false): Promise<OidcDiscovery> {
    if (!force && metadata && dependencies.now() < metadataExpiresAt) return metadata;
    const issuerBase = config.issuer.endsWith('/') ? config.issuer : `${config.issuer}/`;
    const discoveryUrl = new URL('.well-known/openid-configuration', issuerBase).href;
    const payload = await requestJson(discoveryUrl, { headers: { Accept: 'application/json' } });
    if (
      payload.issuer !== config.issuer ||
      !Array.isArray(payload.response_types_supported) || !payload.response_types_supported.includes('code') ||
      !Array.isArray(payload.code_challenge_methods_supported) || !payload.code_challenge_methods_supported.includes('S256') ||
      !Array.isArray(payload.id_token_signing_alg_values_supported) || !payload.id_token_signing_alg_values_supported.includes('RS256') ||
      (payload.grant_types_supported !== undefined &&
        (!Array.isArray(payload.grant_types_supported) || !payload.grant_types_supported.includes('authorization_code')))
    ) {
      throw new OidcAuthenticationError('invalid_response');
    }
    metadata = {
      issuer: config.issuer,
      authorization_endpoint: validateEndpoint(payload.authorization_endpoint, config.allowLoopbackHttp),
      token_endpoint: validateEndpoint(payload.token_endpoint, config.allowLoopbackHttp),
      jwks_uri: validateEndpoint(payload.jwks_uri, config.allowLoopbackHttp),
      response_types_supported: payload.response_types_supported as string[],
      code_challenge_methods_supported: payload.code_challenge_methods_supported as string[],
      id_token_signing_alg_values_supported: payload.id_token_signing_alg_values_supported as string[],
    };
    metadataExpiresAt = dependencies.now() + JWKS_CACHE_MS;
    return metadata;
  }

  async function getSigningKey(kid: string, force = false): Promise<SigningJwk> {
    if (force || !jwks || dependencies.now() >= jwksExpiresAt) {
      const discovery = await getMetadata();
      const payload = await requestJson(discovery.jwks_uri, { headers: { Accept: 'application/json' } });
      if (!Array.isArray(payload.keys) || payload.keys.length === 0 || payload.keys.length > MAX_JWKS_KEYS) {
        throw new OidcAuthenticationError('invalid_response');
      }
      jwks = payload.keys.filter(isRecord) as SigningJwk[];
      jwksExpiresAt = dependencies.now() + JWKS_CACHE_MS;
    }
    const key = jwks.find((candidate) =>
      candidate.kid === kid && candidate.kty === 'RSA' && isRsaSigningKey(candidate),
    );
    if (key) return key;
    if (!force && dependencies.now() - lastUnknownKidRefreshAt >= 30_000) {
      lastUnknownKidRefreshAt = dependencies.now();
      return getSigningKey(kid, true);
    }
    throw new OidcAuthenticationError('verification_failed');
  }

  async function verifyIdToken(idToken: string, expectedNonce: string, transactionCreatedAt: number): Promise<string> {
    if (idToken.length > MAX_ID_TOKEN_LENGTH) throw new OidcAuthenticationError('verification_failed');
    const segments = idToken.split('.');
    if (segments.length !== 3) throw new OidcAuthenticationError('verification_failed');
    const header = decodeJsonPart(segments[0]);
    const claims = decodeJsonPart(segments[1]);
    if (
      header.alg !== 'RS256' || typeof header.kid !== 'string' || !header.kid ||
      (header.typ !== undefined && header.typ !== 'JWT') || header.crit !== undefined
    ) {
      throw new OidcAuthenticationError('verification_failed');
    }
    const signingKey = await getSigningKey(header.kid);
    let importedKey: CryptoKey;
    try {
      importedKey = await dependencies.crypto.subtle.importKey(
        'jwk',
        signingKey,
        { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' },
        false,
        ['verify'],
      );
      const valid = await dependencies.crypto.subtle.verify(
        { name: 'RSASSA-PKCS1-v1_5' },
        importedKey,
        toArrayBuffer(base64UrlDecode(segments[2])),
        toArrayBuffer(new TextEncoder().encode(`${segments[0]}.${segments[1]}`)),
      );
      if (!valid) throw new OidcAuthenticationError('verification_failed');
    } catch (error) {
      if (error instanceof OidcAuthenticationError) throw error;
      throw new OidcAuthenticationError('verification_failed');
    }

    const nowSeconds = Math.floor(dependencies.now() / 1000);
    const skew = config.clockSkewSeconds;
    const audiences = typeof claims.aud === 'string'
      ? [claims.aud]
      : Array.isArray(claims.aud) && claims.aud.every((item) => typeof item === 'string')
        ? claims.aud as string[]
        : [];
    if (
      claims.iss !== config.issuer || !audiences.includes(config.clientId) ||
      (audiences.length > 1 && claims.azp !== config.clientId) ||
      (claims.azp !== undefined && claims.azp !== config.clientId) ||
      typeof claims.exp !== 'number' || !Number.isFinite(claims.exp) || claims.exp <= nowSeconds - skew ||
      typeof claims.iat !== 'number' || !Number.isFinite(claims.iat) ||
      claims.iat > nowSeconds + skew || claims.iat < Math.floor(transactionCreatedAt / 1000) - skew ||
      (claims.nbf !== undefined && (typeof claims.nbf !== 'number' || !Number.isFinite(claims.nbf) || claims.nbf > nowSeconds + skew)) ||
      typeof claims.nonce !== 'string' || !constantTimeEqual(claims.nonce, expectedNonce) ||
      typeof claims.sub !== 'string' || !claims.sub.trim() || claims.sub.length > 255 ||
      /[\u0000-\u001f\u007f]/.test(claims.sub)
    ) {
      throw new OidcAuthenticationError('verification_failed');
    }
    return claims.sub;
  }

  async function signIn(options: OidcSignInOptions = {}): Promise<void> {
    session = null;
    clearTransaction(dependencies.storage);
    const discovery = await getMetadata();
    const random = (length: number) => {
      const bytes = new Uint8Array(length);
      dependencies.crypto.getRandomValues(bytes);
      return base64UrlEncode(bytes);
    };
    const state = random(32);
    const nonce = random(32);
    const codeVerifier = random(32);
    const challenge = base64UrlEncode(new Uint8Array(await dependencies.crypto.subtle.digest(
      'SHA-256', new TextEncoder().encode(codeVerifier),
    )));
    const transaction: AuthTransaction = {
      state,
      nonce,
      codeVerifier,
      createdAt: dependencies.now(),
      returnTo: normalizeReturnTo(options.returnTo, dependencies.location.origin),
    };
    try {
      dependencies.storage.setItem(TRANSACTION_KEY, JSON.stringify(transaction));
    } catch {
      throw new OidcAuthenticationError('provider_unavailable');
    }
    const authorizationUrl = new URL(discovery.authorization_endpoint);
    authorizationUrl.searchParams.set('client_id', config.clientId);
    authorizationUrl.searchParams.set('redirect_uri', config.redirectUri);
    authorizationUrl.searchParams.set('response_type', 'code');
    authorizationUrl.searchParams.set('scope', config.scopes.join(' '));
    authorizationUrl.searchParams.set('state', state);
    authorizationUrl.searchParams.set('nonce', nonce);
    authorizationUrl.searchParams.set('code_challenge', challenge);
    authorizationUrl.searchParams.set('code_challenge_method', 'S256');
    if (options.prompt) authorizationUrl.searchParams.set('prompt', options.prompt);
    dependencies.location.assign(authorizationUrl.href);
  }

  async function completeSignIn(callbackUrl = dependencies.location.href): Promise<OidcSignInResult> {
    let callback: URL;
    try {
      callback = new URL(callbackUrl);
    } catch {
      throw new OidcAuthenticationError('invalid_state');
    }
    const redirect = new URL(config.redirectUri);
    if (callback.origin !== redirect.origin || callback.pathname !== redirect.pathname || callback.hash) {
      throw new OidcAuthenticationError('invalid_state');
    }
    const states = callback.searchParams.getAll('state');
    const codes = callback.searchParams.getAll('code');
    const errors = callback.searchParams.getAll('error');
    const issuers = callback.searchParams.getAll('iss');
    const transaction = readTransaction(dependencies.storage);
    if (!transaction || states.length !== 1 || !constantTimeEqual(states[0], transaction.state)) {
      clearTransaction(dependencies.storage);
      throw new OidcAuthenticationError('invalid_state');
    }
    if (
      !Number.isFinite(transaction.createdAt) || transaction.createdAt > dependencies.now() + 60_000 ||
      dependencies.now() - transaction.createdAt > TRANSACTION_TTL_MS
    ) {
      clearTransaction(dependencies.storage);
      throw new OidcAuthenticationError('expired_transaction');
    }
    let returnTo: string;
    try {
      returnTo = normalizeReturnTo(transaction.returnTo, dependencies.location.origin);
    } catch {
      clearTransaction(dependencies.storage);
      throw new OidcAuthenticationError('invalid_state');
    }
    clearTransaction(dependencies.storage);
    if (issuers.length > 1 || (issuers.length === 1 && issuers[0] !== config.issuer)) {
      throw new OidcAuthenticationError('invalid_state');
    }
    try {
      dependencies.history.replaceState(null, '', config.redirectUri);
    } catch {
      throw new OidcAuthenticationError('invalid_state');
    }
    if (errors.length > 0) throw new OidcAuthenticationError('provider_error');
    if (codes.length !== 1 || !codes[0] || codes[0].length > 4096) {
      throw new OidcAuthenticationError('invalid_response');
    }

    const discovery = await getMetadata();
    let tokenResponse: JsonRecord;
    try {
      const body = new URLSearchParams({
        grant_type: 'authorization_code',
        client_id: config.clientId,
        code: codes[0],
        redirect_uri: config.redirectUri,
        code_verifier: transaction.codeVerifier,
      });
      tokenResponse = await requestJson(discovery.token_endpoint, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: body.toString(),
      });
    } catch (error) {
      if (error instanceof OidcAuthenticationError) throw error;
      throw new OidcAuthenticationError('provider_unavailable');
    }
    if (
      typeof tokenResponse.access_token !== 'string' ||
      !/^[A-Za-z0-9\-._~+/]+=*$/.test(tokenResponse.access_token) ||
      tokenResponse.access_token.length > MAX_ACCESS_TOKEN_LENGTH ||
      typeof tokenResponse.token_type !== 'string' || tokenResponse.token_type.toLowerCase() !== 'bearer' ||
      typeof tokenResponse.expires_in !== 'number' || !Number.isInteger(tokenResponse.expires_in) ||
      tokenResponse.expires_in < 1 || tokenResponse.expires_in > 86400 ||
      typeof tokenResponse.id_token !== 'string' || !tokenResponse.id_token
    ) {
      throw new OidcAuthenticationError('invalid_response');
    }
    const subject = await verifyIdToken(tokenResponse.id_token, transaction.nonce, transaction.createdAt);
    const nextSession: OidcSession = Object.freeze({
      accessToken: tokenResponse.access_token,
      subject,
      expiresAt: Math.floor(dependencies.now() / 1000) + tokenResponse.expires_in,
    });
    session = nextSession;
    return Object.freeze({ session: nextSession, returnTo });
  }

  function getSession(): OidcSession | null {
    if (!session) return null;
    const expiresAtWithSkew = session.expiresAt * 1000 - config.clockSkewSeconds * 1000;
    if (dependencies.now() >= expiresAtWithSkew) {
      session = null;
      return null;
    }
    return session;
  }

  function signOut(): void {
    session = null;
    clearTransaction(dependencies.storage);
  }

  return Object.freeze({ signIn, completeSignIn, getSession, signOut });
}
