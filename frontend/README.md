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

The portal includes an overview, a read-only Organization profile page and an Asset Inventory page. The typed clients are prepared for existing tenant-scoped APIs, but authentication and live tenant-backed data remain unavailable until a trusted browser OIDC session adapter and API deployment are configured.

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
