export type PlatformReadinessState = 'implemented' | 'verified' | 'unconfigured' | 'pending';

export const platformReadiness = [
  {
    id: 'api',
    label: 'Python API',
    detail: 'FastAPI domain routes and tenant-scoped service boundaries are present in source.',
    status: 'Code present',
    state: 'implemented',
  },
  {
    id: 'tenant',
    label: 'Tenant isolation',
    detail: 'OIDC membership resolution and PostgreSQL RLS have automated integration coverage.',
    status: 'CI verified',
    state: 'verified',
  },
  {
    id: 'ai',
    label: 'Advisory AI',
    detail: 'Specialist workflows are implemented; a live model provider is not confirmed.',
    status: 'Provider unconfigured',
    state: 'unconfigured',
  },
  {
    id: 'memory',
    label: 'Persistent memory',
    detail: 'Durable tenant-scoped conversational memory is not implemented.',
    status: 'Not implemented',
    state: 'pending',
  },
] as const satisfies readonly {
  id: 'api' | 'tenant' | 'ai' | 'memory';
  label: string;
  detail: string;
  status: string;
  state: PlatformReadinessState;
}[];
