# AEGIS Web Portal

React + TypeScript + Vite frontend for the AEGIS customer and operations portal.

## Local development

```bash
npm ci
npm test
npm run typecheck
npm run build
npm run dev
```

The production build is generated in `dist/`.

## Deployment

Configure Vercel with **Root Directory = `frontend`**. Use `npm install` or `npm ci` for installation and `npm run build` for the build command. The output directory is `dist`.

The portal includes an overview, Organization profile, Asset Inventory and tenant Member Management pages. A provider-neutral browser OIDC session adapter is implemented, but it is not yet wired into the React shell and no non-production identity provider is configured. Customer pages therefore remain sign-in-required.

## Customer organization profile

The Organization navigation item contains the first customer-portal profile view. It
uses the tenant-scoped `GET /api/v1/tenants/profile` contract and renders only
validated API data. The current preview does not include an OIDC sign-in/session
adapter, so the page deliberately shows an authentication-required state instead
of sample organization details.

When an identity adapter is added, it must pass a short-lived verified access token
and the selected tenant slug to the page. The API resolves membership server-side;
the browser never supplies a tenant UUID. The typed client sends the token in the
Authorization header, uses `X-AEGIS-Tenant` for the selected slug, disables
credential cookies and redirects, and does not persist tokens.

Set `VITE_AEGIS_API_BASE_URL` to the HTTPS API origin (HTTP is allowed only for
loopback development). This public Vite variable must contain no credential. See
`.env.example` for the placeholder format.


## Asset inventory

The Assets navigation item provides a tenant-scoped inventory screen backed by
GET /api/v1/assets, POST /api/v1/assets and PATCH /api/v1/assets/{asset_id}.
It includes offset pagination (50 records per page), search and filters for the
currently loaded page, archived-record visibility, manual registration, and
archive/restore controls.

The client requires a short-lived access token and tenant slug from a future
trusted session adapter. It never sends a tenant UUID, disables credential
cookies and redirects, validates API responses, and sanitizes HTTP errors.
Management controls are shown only when the adapter supplies a server-resolved
tenant role; the backend remains the authorization authority and independently
checks every write.

The page intentionally remains sign-in-required in the current preview. It does
not invent asset records, and it does not claim connector-based discovery or
automatic synchronization.


## Tenant member management

The Members navigation item uses the existing tenant membership API:
- GET /api/v1/tenants/members
- POST /api/v1/tenants/members/invitations
- PATCH /api/v1/tenants/members/{subject}

The page supports member listing, invitations to known OIDC subjects, role changes,
suspension and revocation. Invitations create pending grants and do not send email
or create identity-provider accounts. The page requires a trusted session carrying
the server-resolved tenant-admin role and verified subject; the backend independently
rechecks tenant-admin authority and protects the last active administrator.

Suspension and revocation are shown with explicit confirmation because the current
API has no reactivation, restore or re-invitation operation. The page remains
sign-in-required in the current preview and does not display sample identities.


## Browser OIDC session adapter

`src/auth/oidc.ts` implements a provider-neutral OpenID Connect Authorization Code
flow with PKCE S256. It discovers the issuer metadata, requires the exact configured
issuer, HTTPS endpoints (loopback HTTP only when explicitly enabled for development),
and provider support for authorization code, PKCE S256 and RS256 ID-token signatures.

The adapter verifies the ID-token RS256 signature against the issuer JWKS and checks
issuer, client audience, authorized party (`azp` when multiple audiences are present),
expiry, issue/not-before times and the transaction nonce. The API must independently
verify the access token using its configured issuer, JWKS and API audience; a browser
ID-token check is not API authorization and the browser never assigns tenant roles.

The PKCE verifier, state and nonce are held in `sessionStorage` for a maximum
10-minute redirect transaction. Access and ID tokens are kept in memory only;
refresh tokens are ignored and never persisted. The in-memory session expires with
the access token and requires a new sign-in. `signOut()` clears the local session
only; remote identity-provider single sign-out is not implemented yet.

The adapter is not connected to the app shell yet. To prepare a public SPA client,
register the exact callback URI with the chosen provider and configure these public
Vite variables:

- `VITE_AEGIS_OIDC_ISSUER`
- `VITE_AEGIS_OIDC_CLIENT_ID`
- `VITE_AEGIS_OIDC_REDIRECT_URI`

All three must be present; otherwise configuration remains disabled. The browser
client rejects a `VITE_AEGIS_OIDC_CLIENT_SECRET` rather than accepting a secret in
the public bundle. The provider must allow the portal origin to access its discovery,
JWKS and token endpoints via CORS and issue an access token for the API audience
configured on the backend. No provider, client ID, redirect registration or API
audience has been configured for AEGIS yet. See `.env.example` for safe placeholders.
