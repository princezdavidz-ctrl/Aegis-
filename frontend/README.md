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


## Customer asset inventory

The Assets workspace provides a read-only view over the tenant-scoped
`GET /api/v1/assets` endpoint, including bounded pagination, local search,
asset-type/criticality filters, and an optional archived-record view.

Set `VITE_AEGIS_API_BASE_URL` to the HTTPS API origin (loopback HTTP is allowed
for local development). The browser page intentionally remains in its
sign-in-required state until a trusted OIDC session adapter supplies an
ephemeral access token and tenant slug. Do not put tokens or client secrets in
Vite environment variables or browser storage. Asset creation, editing, and
archiving remain disabled in this UI increment.
