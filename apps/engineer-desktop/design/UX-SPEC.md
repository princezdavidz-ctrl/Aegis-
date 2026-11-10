# AEGIS Engineer Desktop — UX & Visual Design Specification

**Status:** Design proposal / high-fidelity prototype  
**Platform:** Flutter desktop (Windows, macOS, Linux)  
**Audience:** Security operations engineers, SOC leads, incident responders

## Product experience
AEGIS is an operator console, not a customer marketing dashboard. It prioritizes situational awareness, fast investigation, evidence provenance and safe action approval. The interface must distinguish verified live data, delayed data, demo fixtures and unavailable integrations.

### Primary navigation
Overview; Companies; Live Monitoring; Threat Alerts; Investigations; AI Agents; Vulnerabilities; Patch Center; Incidents; Reports; Team & Shifts; Settings.

## Visual direction
Dark, precise, calm, technical and premium. Deep ink canvas, layered slate surfaces, restrained electric-cyan interaction accents, and semantic status colors only where meaning is clear. Avoid neon-green hacker clichés and decorative gradients behind dense data.

### Color tokens
| Token | Value | Use |
|---|---|---|
| canvas | #080D16 | App background |
| surface-1 | #101826 | Sidebar and panels |
| surface-2 | #151F2F | Cards |
| surface-3 | #1B293B | Hover/selected |
| border-subtle | #26364A | Dividers |
| text-primary | #F2F6FC | Main content |
| text-secondary | #A7B5C8 | Supporting copy |
| text-muted | #718198 | Metadata |
| accent | #55C8E8 | Actions, focus, links |
| accent-strong | #239FC4 | Pressed state |
| success | #45C49A | Healthy/verified |
| warning | #E8B45B | Attention |
| danger | #F07878 | Critical/failed |
| info | #83A9F4 | Informational |

### Typography and layout
- Inter or metrically similar sans-serif; tabular numerals for metrics and timestamps.
- Target 1440×900; minimum supported width 1100 px.
- Sidebar 248 px expanded / 72 px collapsed; top bar 68 px.
- 8 px spacing scale; panel radius 12 px; control radius 8 px.
- Body 13–14 px, metadata 12 px, page headings 22–28 px.
- Never rely on color alone to communicate status.

## Overview screen
1. Header: workspace context, global search, time range, notifications and operator menu.
2. KPI row: open alerts, critical findings, protected assets and integrations online. Values must be backend-sourced; show an em dash or Not connected when unavailable.
3. Threat landscape: severity distribution and trend, only when real source data exists.
4. Priority queue: detection, severity, affected asset, authorized workspace, age, owner and state.
5. Recent activity: verified system/analyst actions with actor and timestamp.
6. Integration health: source state, last successful ingest and actionable setup guidance.

## Interaction patterns
- Alert rows open detail; triage requires explicit state transitions.
- AI summaries are labeled AI-assisted, cite evidence and expose confidence/limitations.
- Patch Center shows proposal, diff, scope, test evidence, risk, approver and rollback plan. No one-click autonomous production deployment.
- Tenant switching is explicit and auditable; workspace context remains visible.
- Design empty, loading, stale, partial and error states. Never substitute fabricated telemetry.
- Keyboard navigation, visible focus, tooltips for icon-only controls and minimum 40 px targets.

## Security and trust
- Backend is authoritative for identity, tenant membership, permissions, approvals and audit.
- Never trust a client-supplied tenant ID to authorize access.
- Read-only monitoring by default. Consequential actions require explicit human approval and server-side authorization.
- Clearly distinguish live, delayed, demo and unavailable data.
- AI output is advisory and traceable to evidence. Treat telemetry, tickets, logs and code as untrusted input.
- Never expose secrets, tokens or cross-tenant data in UI, logs or screenshots.

## Responsive desktop behavior
- Below 1280 px, collapse the secondary rail before compressing primary data tables.
- At 1100 px, collapse the left nav to an icon rail.
- Critical actions must never be shortcut-only.

## Implementation handoff
This is the design source of truth for Flutter desktop. The overview HTML is a visual reference, not production code and not connected to services. Implement reusable Flutter tokens and widgets before module-specific layouts. Preserve provider boundaries and backend-authoritative security controls.
