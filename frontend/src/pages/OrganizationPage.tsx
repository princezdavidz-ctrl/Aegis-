import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Building2, CalendarDays, RefreshCw, ShieldCheck } from 'lucide-react';
import {
  createTenantProfileClient,
  TenantProfileApiError,
  type TenantProfile,
  type TenantSession,
} from '../api/tenantProfile';

interface OrganizationPageProps {
  /** Supplied only by a future verified OIDC session adapter. */
  session?: TenantSession;
}

const apiBaseUrl = import.meta.env.VITE_AEGIS_API_BASE_URL?.trim() ?? '';

function profileErrorMessage(error: unknown): string {
  if (error instanceof TenantProfileApiError && error.status === 401) {
    return 'Your session is not valid. Sign in again before viewing this organization.';
  }
  if (error instanceof TenantProfileApiError && error.status === 403) {
    return 'Your account does not have access to the selected organization.';
  }
  return 'The organization profile could not be loaded. Check the service connection and try again.';
}

function DetailCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-[#0d141e] p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">{label}</p>
      <p className="mt-2 break-words text-sm font-medium text-slate-200">{value}</p>
    </div>
  );
}

function ConnectionState({
  title,
  description,
  icon: Icon = Building2,
}: {
  title: string;
  description: string;
  icon?: typeof Building2;
}) {
  return (
    <section aria-labelledby="organization-heading" className="mx-auto flex min-h-[420px] max-w-3xl flex-col items-center justify-center rounded-2xl border border-white/[0.07] bg-[#101722] p-8 text-center">
      <span className="grid size-12 place-items-center rounded-2xl border border-cyan-200/15 bg-cyan-300/[0.07] text-cyan-200">
        <Icon size={23} aria-hidden="true" />
      </span>
      <p className="mt-5 text-[10px] font-semibold uppercase tracking-[0.15em] text-amber-200">Organization workspace</p>
      <h2 id="organization-heading" className="mt-3 text-xl font-semibold text-white">{title}</h2>
      <p className="mt-2 max-w-lg text-sm leading-6 text-slate-500">{description}</p>
    </section>
  );
}

export function OrganizationPage({ session }: OrganizationPageProps) {
  const clientConfig = useMemo(() => {
    if (!apiBaseUrl) return { state: 'missing' as const };
    try {
      return { state: 'ready' as const, client: createTenantProfileClient(apiBaseUrl) };
    } catch {
      return { state: 'invalid' as const };
    }
  }, []);

  const [profile, setProfile] = useState<TenantProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    if (!session || clientConfig.state !== 'ready') return;

    let active = true;
    setLoading(true);
    setError(null);

    clientConfig.client.getProfile(session)
      .then((result) => {
        if (active) setProfile(result);
      })
      .catch((reason: unknown) => {
        if (active) setError(profileErrorMessage(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [session, clientConfig, retryCount]);

  if (!session) {
    return (
      <ConnectionState
        title="Connect your organization account"
        description="Organization details are loaded only after a trusted sign-in and server-side membership check. Authentication is not connected in this preview, so no sample organization data is displayed."
      />
    );
  }

  if (clientConfig.state === 'missing') {
    return (
      <ConnectionState
        title="API connection is not configured"
        description="Set VITE_AEGIS_API_BASE_URL to the HTTPS API origin. Access tokens must come from the identity provider at runtime and must never be stored in Vite environment variables."
        icon={AlertCircle}
      />
    );
  }

  if (clientConfig.state === 'invalid') {
    return (
      <ConnectionState
        title="API configuration is invalid"
        description="The API origin must use HTTPS. HTTP is accepted only for localhost development, and URL credentials or path prefixes are not allowed."
        icon={AlertCircle}
      />
    );
  }

  if (loading) {
    return (
      <section aria-live="polite" className="rounded-2xl border border-white/[0.07] bg-[#101722] p-8">
        <p className="text-sm text-slate-300">Loading organization profile…</p>
      </section>
    );
  }

  if (error) {
    return (
      <section role="alert" className="rounded-2xl border border-amber-200/15 bg-[#171923] p-8">
        <div className="flex items-center gap-2 text-amber-200"><AlertCircle size={17} aria-hidden="true" /><h2 className="text-sm font-semibold">Organization profile unavailable</h2></div>
        <p className="mt-3 text-sm leading-6 text-slate-400">{error}</p>
        <button type="button" onClick={() => setRetryCount((count) => count + 1)} className="mt-5 inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-200 hover:bg-white/5">
          <RefreshCw size={13} aria-hidden="true" /> Retry
        </button>
      </section>
    );
  }

  if (!profile) {
    return (
      <ConnectionState
        title="Organization profile is unavailable"
        description="The service returned no organization profile. No local or fabricated profile has been substituted."
        icon={AlertCircle}
      />
    );
  }

  return (
    <section aria-labelledby="organization-heading" className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-200">Customer workspace</p>
          <h2 id="organization-heading" className="mt-2 text-2xl font-semibold text-white">{profile.display_name}</h2>
          <p className="mt-1 text-sm text-slate-500">Organization profile · {profile.slug}</p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300/15 bg-emerald-300/[0.06] px-3 py-2 text-[11px] text-emerald-200">
          <ShieldCheck size={13} aria-hidden="true" /> Tenant membership verified
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <DetailCard label="Industry" value={profile.industry ?? 'Not set'} />
        <DetailCard label="Organization size" value={profile.organization_size ?? 'Not set'} />
        <DetailCard label="Region preference" value={profile.region ?? 'Not set'} />
        <DetailCard label="Policy profile" value={profile.policy_profile} />
        <DetailCard label="Data retention preference" value={`${profile.data_retention_days} days`} />
        <DetailCard label="Created" value={new Date(profile.created_at).toISOString().slice(0, 10)} />
      </div>

      <div className="flex items-start gap-3 rounded-xl border border-white/[0.07] bg-[#0e141e] p-4">
        <CalendarDays size={16} className="mt-0.5 text-slate-400" aria-hidden="true" />
        <p className="text-xs leading-5 text-slate-500">Region and retention are organization preferences. They do not by themselves prove data residency or automatic deletion enforcement.</p>
      </div>
    </section>
  );
}
