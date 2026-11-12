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

The current UI is a frontend foundation. Authentication, tenant-backed data, API workflows and production operations are not yet connected.

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
