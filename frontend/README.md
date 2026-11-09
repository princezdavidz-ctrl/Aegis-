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
