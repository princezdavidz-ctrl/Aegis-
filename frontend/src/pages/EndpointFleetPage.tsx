import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle, Copy, Laptop, Monitor, Plus, RefreshCw, ShieldCheck, ShieldOff,
} from 'lucide-react';
import {
  createEndpointClient, EndpointApiError, type EndpointDevice, type EndpointInvitation, type EndpointPlatform,
} from '../api/endpoints';
import type { TenantSession } from '../api/tenantProfile';

interface EndpointFleetPageProps {
  session?: TenantSession & { membershipRole?: string };
}

const apiBaseUrl = import.meta.env.VITE_AEGIS_API_BASE_URL?.trim() ?? '';
const platformLabels: Record<EndpointPlatform, string> = {
  windows: 'Windows', linux: 'Linux', macos: 'macOS',
};

function timeLabel(value: string | null): string {
  if (!value) return 'Never';
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function errorLabel(error: unknown): string {
  if (error instanceof EndpointApiError && error.status === 401) return 'Your session expired. Sign in again to view endpoint devices.';
  if (error instanceof EndpointApiError && error.status === 403) return 'Your organization role does not permit endpoint fleet access.';
  return 'The endpoint fleet could not be loaded. Check the API connection and retry.';
}

export function EndpointFleetPage({ session }: EndpointFleetPageProps) {
  const config = useMemo(() => {
    if (!apiBaseUrl) return { state: 'missing' as const };
    try { return { state: 'ready' as const, client: createEndpointClient(apiBaseUrl) }; }
    catch { return { state: 'invalid' as const }; }
  }, []);
  const [devices, setDevices] = useState<EndpointDevice[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [invitationPlatform, setInvitationPlatform] = useState<EndpointPlatform>('linux');
  const [invitationTtl, setInvitationTtl] = useState(60);
  const [issuingInvitation, setIssuingInvitation] = useState(false);
  const [issuedInvitation, setIssuedInvitation] = useState<EndpointInvitation | null>(null);
  const canManage = session?.membershipRole === 'tenant_admin' || session?.membershipRole === 'security_manager';

  const refresh = useCallback(() => setRetry((value) => value + 1), []);

  useEffect(() => {
    if (!session || config.state !== 'ready') return;
    let active = true;
    setLoading(true);
    setError(null);
    config.client.listDevices(session, 100)
      .then((result) => { if (active) setDevices(result.items); })
      .catch((reason: unknown) => { if (active) setError(errorLabel(reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [session, config, retry]);

  async function issueInvitation(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || config.state !== 'ready' || !canManage || issuingInvitation) return;
    setIssuingInvitation(true);
    setError(null);
    setNotice(null);
    setIssuedInvitation(null);
    try {
      const invitation = await config.client.createInvitation(session, invitationPlatform, invitationTtl);
      setIssuedInvitation(invitation);
      setNotice('One-time enrollment invitation created. Copy the token now; it will not be shown again after leaving this page.');
    } catch (reason) {
      setError(errorLabel(reason));
    } finally {
      setIssuingInvitation(false);
    }
  }

  async function revoke(device: EndpointDevice) {
    if (!session || config.state !== 'ready' || !canManage || device.status !== 'active') return;
    if (!window.confirm('Revoke ' + device.hostname + '? The device will no longer be able to submit telemetry.')) return;
    setBusyId(device.device_id);
    setError(null);
    setNotice(null);
    try {
      await config.client.revokeDevice(session, device.device_id);
      setNotice(device.hostname + ' was revoked.');
      refresh();
    } catch (reason) {
      setError(errorLabel(reason));
    } finally {
      setBusyId(null);
    }
  }

  if (!session) return <State title="Connect your organization account" body="Endpoint inventory is available only after trusted sign-in and a server-side membership check. No demo devices or tenant identifiers are shown." />;
  if (config.state !== 'ready') return <State title={config.state === 'missing' ? 'API connection is not configured' : 'API configuration is invalid'} body="Configure VITE_AEGIS_API_BASE_URL with the HTTPS API origin. Access tokens must come from the trusted OIDC session and must never be placed in Vite environment variables." />;
  if (loading && devices.length === 0) return <div role="status" className="flex min-h-64 items-center justify-center gap-3 text-sm text-slate-400"><RefreshCw size={17} className="animate-spin text-cyan-200" />Loading endpoint fleet…</div>;
  if (error && devices.length === 0) return <State title="Endpoint fleet unavailable" body={error} action={refresh} />;

  return (
    <section aria-labelledby="endpoint-fleet-title" className="space-y-5">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div><p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-cyan-200">Phase 11 · Endpoint security</p><h2 id="endpoint-fleet-title" className="mt-2 text-xl font-semibold text-white">Endpoint fleet</h2><p className="mt-1 text-sm text-slate-500">Tenant-scoped device inventory, telemetry freshness and enrollment health.</p></div>
        <button type="button" onClick={refresh} disabled={loading} className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 px-4 py-2.5 text-xs text-slate-200 disabled:opacity-50"><RefreshCw size={14} />Refresh fleet</button>
      </div>
      {error && <p role="alert" className="rounded-xl border border-rose-200/15 bg-rose-300/[0.05] px-4 py-3 text-xs text-rose-100">{error}</p>}
      {notice && <p role="status" className="rounded-xl border border-emerald-200/15 bg-emerald-300/[0.05] px-4 py-3 text-xs text-emerald-100">{notice}</p>}
      {canManage && <section className="rounded-2xl border border-white/[0.07] bg-[#101722] p-5">
        <div className="flex items-center gap-2"><Plus size={16} className="text-cyan-200" /><h3 className="text-sm font-semibold text-white">Enroll an endpoint</h3></div>
        <p className="mt-1 text-xs text-slate-500">Create a single-use enrollment token for a specific operating system. The raw token is displayed once and is never stored by the browser beyond this page state.</p>
        <form onSubmit={(event) => void issueInvitation(event)} className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="flex-1 text-xs text-slate-400">Platform
            <select value={invitationPlatform} onChange={(event) => setInvitationPlatform(event.target.value as EndpointPlatform)} disabled={issuingInvitation} className="mt-1 block w-full rounded-lg border border-white/10 bg-[#0d141e] px-3 py-2.5 text-sm text-white">
              <option value="windows">Windows</option><option value="linux">Linux</option><option value="macos">macOS</option>
            </select>
          </label>
          <label className="flex-1 text-xs text-slate-400">Expires after
            <select value={invitationTtl} onChange={(event) => setInvitationTtl(Number(event.target.value))} disabled={issuingInvitation} className="mt-1 block w-full rounded-lg border border-white/10 bg-[#0d141e] px-3 py-2.5 text-sm text-white">
              <option value={15}>15 minutes</option><option value={60}>1 hour</option><option value={360}>6 hours</option><option value={1440}>24 hours</option>
            </select>
          </label>
          <button type="submit" disabled={issuingInvitation} className="inline-flex items-center justify-center gap-2 rounded-xl border border-cyan-200/20 bg-cyan-200/[0.08] px-4 py-2.5 text-xs font-medium text-cyan-100 disabled:opacity-50"><Plus size={14} />{issuingInvitation ? 'Creating…' : 'Create invitation'}</button>
        </form>
        {issuedInvitation && <div className="mt-4 rounded-xl border border-cyan-200/15 bg-cyan-200/[0.04] p-4">
          <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-semibold text-cyan-100">One-time enrollment token · {platformLabels[issuedInvitation.platform]}</p><span className="text-[10px] text-slate-500">Expires {timeLabel(issuedInvitation.expires_at)}</span></div>
          <code className="mt-3 block break-all rounded-lg bg-black/20 p-3 text-xs text-white">{issuedInvitation.enrollment_token}</code>
          <button type="button" onClick={() => { void window.navigator.clipboard.writeText(issuedInvitation.enrollment_token).then(() => setNotice('Enrollment token copied to clipboard.')).catch(() => setError('Clipboard access was unavailable. Select and copy the token manually.')); }} className="mt-3 inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-200"><Copy size={13} />Copy token</button>
          <p className="mt-2 text-[10px] text-amber-200/80">Treat this token as a secret. It can enroll one matching-platform device and cannot be retrieved again.</p>
        </div>}
      </section>}
      <div className="grid gap-4 sm:grid-cols-3">
        <Metric label="Registered devices" value={String(devices.length)} icon={Monitor} />
        <Metric label="Online devices" value={String(devices.filter((d) => d.health_status === 'online').length)} icon={ShieldCheck} />
        <Metric label="Needs attention" value={String(devices.filter((d) => ['stale', 'offline', 'never_reported'].includes(d.health_status)).length)} icon={AlertCircle} />
      </div>
      <div className="overflow-hidden rounded-2xl border border-white/[0.07] bg-[#101722]">
        <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-4"><h3 className="text-xs font-semibold text-slate-200">Managed endpoints</h3><span className="text-[10px] text-slate-500">Up to 100 devices</span></div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[850px] text-left text-xs">
            <caption className="sr-only">Organization endpoint devices and telemetry health</caption>
            <thead className="bg-[#0d141e] text-[10px] uppercase tracking-[0.12em] text-slate-500"><tr><th scope="col" className="px-5 py-3">Device</th><th scope="col" className="px-4 py-3">Platform</th><th scope="col" className="px-4 py-3">Agent</th><th scope="col" className="px-4 py-3">Last heartbeat</th><th scope="col" className="px-4 py-3">Last event</th><th scope="col" className="px-4 py-3">Health</th><th scope="col" className="px-4 py-3">Device</th>{canManage && <th scope="col" className="px-4 py-3">Action</th>}</tr></thead>
            <tbody className="divide-y divide-white/[0.05]">
              {devices.map((device) => (
                <tr key={device.device_id} className="text-slate-300">
                  <td className="px-5 py-4"><p className="font-medium text-white">{device.hostname}</p><p className="mt-1 text-[10px] text-slate-600">{device.device_id}</p></td>
                  <td className="px-4 py-4">{platformLabels[device.platform]}</td>
                  <td className="px-4 py-4">{device.agent_version}</td>
                  <td className="px-4 py-4">{timeLabel(device.last_heartbeat_at)}</td>
                  <td className="px-4 py-4"><p>{device.last_event_type ?? 'No events'}</p><p className="mt-1 text-[10px] text-slate-600">{timeLabel(device.last_event_received_at)}</p></td>
                  <td className="px-4 py-4"><HealthPill status={device.health_status} /></td><td className="px-4 py-4"><span className={device.status === 'active' ? 'text-emerald-200' : 'text-slate-500'}>{device.status}</span></td>
                  {canManage && <td className="px-4 py-4"><button type="button" disabled={device.status !== 'active' || busyId === device.device_id} onClick={() => void revoke(device)} className="rounded-lg border border-rose-200/15 px-2.5 py-2 text-[10px] text-rose-200 disabled:cursor-not-allowed disabled:opacity-40">{busyId === device.device_id ? 'Revoking…' : 'Revoke'}</button></td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {devices.length === 0 && <div className="px-5 py-14 text-center"><Laptop size={24} className="mx-auto text-slate-600" /><h3 className="mt-3 text-sm font-medium text-slate-300">No enrolled endpoints</h3><p className="mt-1 text-xs text-slate-500">Create an enrollment invitation through the secured endpoint API to register the first device.</p></div>}
      </div>
      <p className="text-[10px] leading-5 text-slate-600">Device inventory is read from the verified tenant context. Revocation requires a tenant administrator or security manager and is recorded by the backend audit service.</p>
    </section>
  );
}


function HealthPill({ status }: { status: import('../api/endpoints').EndpointHealthStatus }) {
  const styles: Record<typeof status, string> = {
    online: 'text-emerald-200 bg-emerald-300/10',
    stale: 'text-amber-200 bg-amber-300/10',
    offline: 'text-rose-200 bg-rose-300/10',
    never_reported: 'text-slate-300 bg-slate-300/10',
    revoked: 'text-slate-500 bg-slate-500/10',
  };
  const labels: Record<typeof status, string> = {
    online: 'Online', stale: 'Stale', offline: 'Offline',
    never_reported: 'Never reported', revoked: 'Revoked',
  };
  return <span className={'inline-flex rounded-full px-2.5 py-1 text-[10px] font-medium ' + styles[status]}>{labels[status]}</span>;
}

function Metric({ label, value, icon: Icon }: { label: string; value: string; icon: typeof Monitor }) {
  return <article className="rounded-2xl border border-white/[0.07] bg-[#101722] p-5"><div className="flex items-center justify-between"><p className="text-xs text-slate-500">{label}</p><Icon size={16} className="text-cyan-200" /></div><p className="mt-3 text-2xl font-semibold tabular-nums text-white">{value}</p></article>;
}

function State({ title, body, action }: { title: string; body: string; action?: () => void }) {
  return <section className="mx-auto flex min-h-[400px] max-w-3xl flex-col items-center justify-center rounded-2xl border border-white/[0.07] bg-[#101722] p-8 text-center"><AlertCircle size={25} className="text-amber-200" /><h2 className="mt-4 text-xl font-semibold text-white">{title}</h2><p className="mt-2 max-w-lg text-sm leading-6 text-slate-500">{body}</p>{action && <button type="button" onClick={action} className="mt-5 rounded-xl border border-cyan-200/15 px-4 py-2.5 text-xs text-cyan-100">Retry</button>}</section>;
}
