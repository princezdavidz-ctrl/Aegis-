/**
 * Source-code maturity metadata for the overview panel.
 *
 * These values describe repository implementation state, not live service
 * health. Runtime availability must come from authenticated health checks
 * before the UI is allowed to display it as operational.
 */
export type PlatformReadinessId =
  | 'api'
  | 'orchestration'
  | 'model-provider'
  | 'memory';

export type PlatformReadinessState =
  | 'code_present'
  | 'not_configured'
  | 'not_implemented';

export interface PlatformReadinessItem {
  id: PlatformReadinessId;
  label: string;
  detail: string;
  state: PlatformReadinessState;
  stateLabel: string;
}

export const platformReadiness: readonly PlatformReadinessItem[] = [
  {
    id: 'api',
    label: 'Python API',
    detail: 'FastAPI service, OIDC verification and tenant-scoped data boundaries',
    state: 'code_present',
    stateLabel: 'Code present · deployment unverified',
  },
  {
    id: 'orchestration',
    label: 'AI orchestration',
    detail: 'Provider-neutral gateway and advisory specialist workflows',
    state: 'code_present',
    stateLabel: 'Code present · advisory only',
  },
  {
    id: 'model-provider',
    label: 'Model provider',
    detail: 'OpenAI-compatible adapter; live provider settings are absent',
    state: 'not_configured',
    stateLabel: 'Adapter present · not configured',
  },
  {
    id: 'memory',
    label: 'Memory store',
    detail: 'Persistent tenant-scoped memory and retrieval are not implemented',
    state: 'not_implemented',
    stateLabel: 'Not implemented',
  },
];
