import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import {
  AlertCircle,
  Archive,
  ArchiveRestore,
  Boxes,
  ChevronLeft,
  ChevronRight,
  Plus,
  RefreshCw,
  Search,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import {
  ASSET_CRITICALITIES,
  ASSET_ENVIRONMENTS,
  ASSET_TYPES,
  AssetApiError,
  createAssetClient,
  type AssetCreateInput,
  type AssetEnvironment,
  type AssetRecord,
  type AssetSession,
  type AssetType,
} from '../api/assets';

interface AssetInventoryPageProps {
  /** Supplied only by a future trusted browser session and membership adapter. */
  session?: AssetSession;
}

const apiBaseUrl = import.meta.env.VITE_AEGIS_API_BASE_URL?.trim() ?? '';
const PAGE_SIZE = 50;

const initialForm: AssetCreateInput = {
  name: '',
  asset_type: 'endpoint',
  external_id: null,
  environment: 'unknown',
  criticality: 'medium',
};

function humanize(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}

function dateLabel(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function requestErrorMessage(error: unknown): string {
  if (error instanceof AssetApiError && error.status === 401) {
    return 'Your session is not valid. Sign in again before viewing this inventory.';
  }
  if (error instanceof AssetApiError && error.status === 403) {
    return 'Your account does not have access to this organization’s asset inventory.';
  }
  return 'The asset inventory could not be loaded. Check the service connection and try again.';
}

function StatePanel({
  title,
  description,
  icon: Icon = Boxes,
}: {
  title: string;
  description: string;
  icon?: LucideIcon;
}) {
  return (
    <section aria-labelledby="assets-heading" className="mx-auto flex min-h-[420px] max-w-3xl flex-col items-center justify-center rounded-2xl border border-white/[0.07] bg-[#101722] p-8 text-center">
      <span className="grid size-12 place-items-center rounded-2xl border border-cyan-200/15 bg-cyan-300/[0.07] text-cyan-200">
        <Icon size={23} aria-hidden="true" />
      </span>
      <p className="mt-5 text-[10px] font-semibold uppercase tracking-[0.15em] text-amber-200">Asset inventory</p>
      <h2 id="assets-heading" className="mt-3 text-xl font-semibold text-white">{title}</h2>
      <p className="mt-2 max-w-lg text-sm leading-6 text-slate-500">{description}</p>
    </section>
  );
}

function criticalityClass(value: AssetRecord['criticality']): string {
  if (value === 'critical') return 'border-rose-300/20 bg-rose-300/[0.08] text-rose-200';
  if (value === 'high') return 'border-amber-300/20 bg-amber-300/[0.08] text-amber-200';
  if (value === 'medium') return 'border-cyan-300/20 bg-cyan-300/[0.08] text-cyan-200';
  return 'border-slate-400/20 bg-slate-400/[0.08] text-slate-300';
}

export function AssetInventoryPage({ session }: AssetInventoryPageProps) {
  const clientConfig = useMemo(() => {
    if (!apiBaseUrl) return { state: 'missing' as const };
    try {
      return { state: 'ready' as const, client: createAssetClient(apiBaseUrl) };
    } catch {
      return { state: 'invalid' as const };
    }
  }, []);

  const [assets, setAssets] = useState<AssetRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<'all' | AssetType>('all');
  const [environmentFilter, setEnvironmentFilter] = useState<'all' | AssetEnvironment>('all');
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<AssetCreateInput>(initialForm);
  const [saving, setSaving] = useState(false);
  const [busyAssetId, setBusyAssetId] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [mutationSuccess, setMutationSuccess] = useState<string | null>(null);

  const canManageAssets = session?.membershipRole === 'tenant_admin' ||
    session?.membershipRole === 'security_manager';

  useEffect(() => {
    if (!session || clientConfig.state !== 'ready') return;

    let active = true;
    setLoading(true);
    setError(null);

    clientConfig.client.listAssets(session, {
      limit: PAGE_SIZE,
      offset,
      includeArchived,
    })
      .then((result) => {
        if (active) setAssets(result);
      })
      .catch((reason: unknown) => {
        if (active) setError(requestErrorMessage(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [session, clientConfig, offset, includeArchived, retryCount]);

  const filteredAssets = useMemo(() => {
    const query = search.trim().toLowerCase();
    return assets.filter((asset) => {
      const matchesSearch = !query ||
        asset.name.toLowerCase().includes(query) ||
        humanize(asset.asset_type).toLowerCase().includes(query) ||
        (asset.external_id?.toLowerCase().includes(query) ?? false);
      const matchesType = typeFilter === 'all' || asset.asset_type === typeFilter;
      const matchesEnvironment = environmentFilter === 'all' || asset.environment === environmentFilter;
      return matchesSearch && matchesType && matchesEnvironment;
    });
  }, [assets, search, typeFilter, environmentFilter]);

  async function registerAsset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || clientConfig.state !== 'ready' || !canManageAssets) return;

    setSaving(true);
    setMutationError(null);
    setMutationSuccess(null);
    try {
      await clientConfig.client.createAsset(session, form);
      setForm(initialForm);
      setShowForm(false);
      setOffset(0);
      setRetryCount((value) => value + 1);
      setMutationSuccess('Asset registered and recorded in the audit trail.');
    } catch {
      setMutationError('The asset could not be registered. Check your role and service connection, then try again.');
    } finally {
      setSaving(false);
    }
  }

  async function changeAssetStatus(asset: AssetRecord) {
    if (!session || clientConfig.state !== 'ready' || !canManageAssets) return;

    setBusyAssetId(asset.id);
    setMutationError(null);
    setMutationSuccess(null);
    const nextStatus = asset.status === 'active' ? 'archived' : 'active';
    try {
      await clientConfig.client.updateAsset(session, asset.id, { status: nextStatus });
      setRetryCount((value) => value + 1);
      setMutationSuccess(nextStatus === 'archived' ? 'Asset archived.' : 'Asset restored.');
    } catch {
      setMutationError('The asset status could not be changed. Check your role and service connection, then try again.');
    } finally {
      setBusyAssetId(null);
    }
  }

  if (!session) {
    return (
      <StatePanel
        title="Connect your organization account"
        description="Asset records are loaded only after a trusted sign-in and server-side membership check. Authentication is not connected in this preview, so no sample assets or tenant identifiers are displayed."
      />
    );
  }

  if (clientConfig.state === 'missing') {
    return (
      <StatePanel
        title="API connection is not configured"
        description="Set VITE_AEGIS_API_BASE_URL to the HTTPS API origin. Access tokens must come from the identity provider at runtime and must never be stored in Vite environment variables."
        icon={AlertCircle}
      />
    );
  }

  if (clientConfig.state === 'invalid') {
    return (
      <StatePanel
        title="API configuration is invalid"
        description="The API origin must use HTTPS. HTTP is accepted only for localhost development, and URL credentials or path prefixes are not allowed."
        icon={AlertCircle}
      />
    );
  }

  if (loading && assets.length === 0) {
    return (
      <section aria-live="polite" className="flex min-h-[320px] items-center justify-center gap-3 text-sm text-slate-400">
        <RefreshCw size={17} className="animate-spin text-cyan-200" aria-hidden="true" />
        Loading tenant asset inventory…
      </section>
    );
  }

  if (error && assets.length === 0) {
    return (
      <div>
        <StatePanel title="Inventory is unavailable" description={error} icon={AlertCircle} />
        <div className="mt-4 text-center">
          <button type="button" onClick={() => setRetryCount((value) => value + 1)} className="inline-flex items-center gap-2 rounded-xl border border-cyan-200/15 px-4 py-2.5 text-xs text-cyan-100">
            <RefreshCw size={14} aria-hidden="true" /> Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <section aria-labelledby="asset-inventory-heading" className="space-y-5">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <div className="flex items-center gap-2 text-cyan-200">
            <Boxes size={17} aria-hidden="true" />
            <span className="text-[10px] font-semibold uppercase tracking-[0.15em]">Customer inventory</span>
          </div>
          <h2 id="asset-inventory-heading" className="mt-2 text-xl font-semibold text-white">Asset inventory</h2>
          <p className="mt-1 text-xs leading-5 text-slate-500">A tenant-scoped register of approved technology assets. Discovery and automatic synchronization are not connected.</p>
        </div>
        {canManageAssets && (
          <button type="button" onClick={() => setShowForm((value) => !value)} className="inline-flex items-center justify-center gap-2 rounded-xl border border-cyan-200/20 bg-cyan-300/[0.08] px-4 py-2.5 text-xs font-medium text-cyan-100 hover:bg-cyan-300/[0.13]">
            <Plus size={15} aria-hidden="true" /> Register asset
          </button>
        )}
      </div>

      {session.membershipRole && !canManageAssets && (
        <p className="rounded-xl border border-white/[0.07] bg-[#101722] px-4 py-3 text-xs text-slate-400">
          Read-only access. Asset registration and lifecycle changes require the tenant administrator or security manager role.
        </p>
      )}
      {!session.membershipRole && (
        <p className="rounded-xl border border-amber-300/15 bg-amber-300/[0.05] px-4 py-3 text-xs text-amber-100">
          Management controls are hidden until a trusted session adapter supplies the server-resolved tenant role. The API independently enforces every write permission.
        </p>
      )}

      {showForm && canManageAssets && (
        <form onSubmit={registerAsset} className="rounded-2xl border border-cyan-200/15 bg-[#101722] p-5">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-white">Register a manual asset</h3>
              <p className="mt-1 text-xs text-slate-500">Registration is tenant-scoped and audited by the API.</p>
            </div>
            <button type="button" onClick={() => setShowForm(false)} className="text-xs text-slate-400 hover:text-white">Cancel</button>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <label className="text-xs text-slate-400">Asset name
              <input required maxLength={160} value={form.name} onChange={(event) => setForm((value) => ({ ...value, name: event.target.value }))} className="mt-2 w-full rounded-lg border border-white/[0.09] bg-[#0b1018] px-3 py-2.5 text-sm text-white outline-none focus:border-cyan-200/40" />
            </label>
            <label className="text-xs text-slate-400">Asset type
              <select value={form.asset_type} onChange={(event) => setForm((value) => ({ ...value, asset_type: event.target.value as AssetType }))} className="mt-2 w-full rounded-lg border border-white/[0.09] bg-[#0b1018] px-3 py-2.5 text-sm text-white">
                {ASSET_TYPES.map((type) => <option key={type} value={type}>{humanize(type)}</option>)}
              </select>
            </label>
            <label className="text-xs text-slate-400">External identifier (optional)
              <input maxLength={160} value={form.external_id ?? ''} onChange={(event) => setForm((value) => ({ ...value, external_id: event.target.value || null }))} className="mt-2 w-full rounded-lg border border-white/[0.09] bg-[#0b1018] px-3 py-2.5 text-sm text-white outline-none focus:border-cyan-200/40" />
            </label>
            <label className="text-xs text-slate-400">Environment
              <select value={form.environment} onChange={(event) => setForm((value) => ({ ...value, environment: event.target.value as AssetEnvironment }))} className="mt-2 w-full rounded-lg border border-white/[0.09] bg-[#0b1018] px-3 py-2.5 text-sm text-white">
                {ASSET_ENVIRONMENTS.map((environment) => <option key={environment} value={environment}>{humanize(environment)}</option>)}
              </select>
            </label>
            <label className="text-xs text-slate-400">Criticality
              <select value={form.criticality} onChange={(event) => setForm((value) => ({ ...value, criticality: event.target.value as AssetCreateInput['criticality'] }))} className="mt-2 w-full rounded-lg border border-white/[0.09] bg-[#0b1018] px-3 py-2.5 text-sm text-white">
                {ASSET_CRITICALITIES.map((criticality) => <option key={criticality} value={criticality}>{humanize(criticality)}</option>)}
              </select>
            </label>
          </div>
          {mutationError && <p role="alert" className="mt-4 text-xs text-rose-200">{mutationError}</p>}
          <div className="mt-5 flex justify-end">
            <button type="submit" disabled={saving || !form.name.trim()} className="rounded-xl bg-cyan-300 px-4 py-2.5 text-xs font-semibold text-slate-950 disabled:cursor-not-allowed disabled:opacity-50">
              {saving ? 'Registering…' : 'Save asset'}
            </button>
          </div>
        </form>
      )}

      {mutationSuccess && <p role="status" className="rounded-xl border border-emerald-300/15 bg-emerald-300/[0.05] px-4 py-3 text-xs text-emerald-100">{mutationSuccess}</p>}
      {mutationError && !showForm && <p role="alert" className="rounded-xl border border-rose-300/15 bg-rose-300/[0.05] px-4 py-3 text-xs text-rose-100">{mutationError}</p>}
      {error && assets.length > 0 && <p role="alert" className="rounded-xl border border-rose-300/15 bg-rose-300/[0.05] px-4 py-3 text-xs text-rose-100">{error} <button type="button" onClick={() => setRetryCount((value) => value + 1)} className="ml-2 underline">Retry</button></p>}

      <div className="rounded-2xl border border-white/[0.07] bg-[#101722] p-4 sm:p-5">
        <div className="grid gap-3 md:grid-cols-[minmax(220px,1fr)_180px_180px_auto]">
          <label className="relative block text-xs text-slate-500">Search current page
            <Search size={15} className="absolute left-3 top-[34px] text-slate-500" aria-hidden="true" />
            <input aria-label="Search current page" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Name, type or external ID" className="mt-2 w-full rounded-lg border border-white/[0.09] bg-[#0b1018] py-2.5 pl-9 pr-3 text-sm text-white outline-none focus:border-cyan-200/40" />
          </label>
          <label className="text-xs text-slate-500">Asset type
            <select aria-label="Filter by asset type" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value as 'all' | AssetType)} className="mt-2 w-full rounded-lg border border-white/[0.09] bg-[#0b1018] px-3 py-2.5 text-sm text-white">
              <option value="all">All types</option>
              {ASSET_TYPES.map((type) => <option key={type} value={type}>{humanize(type)}</option>)}
            </select>
          </label>
          <label className="text-xs text-slate-500">Environment
            <select aria-label="Filter by environment" value={environmentFilter} onChange={(event) => setEnvironmentFilter(event.target.value as 'all' | AssetEnvironment)} className="mt-2 w-full rounded-lg border border-white/[0.09] bg-[#0b1018] px-3 py-2.5 text-sm text-white">
              <option value="all">All environments</option>
              {ASSET_ENVIRONMENTS.map((environment) => <option key={environment} value={environment}>{humanize(environment)}</option>)}
            </select>
          </label>
          <label className="flex items-end gap-2 pb-2 text-xs text-slate-400">
            <input type="checkbox" checked={includeArchived} onChange={(event) => { setIncludeArchived(event.target.checked); setOffset(0); }} className="size-4 accent-cyan-300" />
            Include archived
          </label>
        </div>
        <p className="mt-3 text-[11px] text-slate-600">Search and filters apply to the currently loaded page. The API uses offset pagination and does not yet return a total count.</p>
      </div>

      <div className="overflow-hidden rounded-2xl border border-white/[0.07] bg-[#101722]">
        <div className="flex flex-col justify-between gap-2 border-b border-white/[0.06] px-5 py-4 sm:flex-row sm:items-center">
          <p className="text-xs font-medium text-slate-300">{filteredAssets.length} matching records on this page</p>
          <p className="text-[11px] text-slate-600">Page {Math.floor(offset / PAGE_SIZE) + 1} · {assets.length} returned by API</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[850px] text-left text-xs">
            <caption className="sr-only">Tenant asset inventory</caption>
            <thead className="bg-[#0d141e] text-[10px] uppercase tracking-[0.12em] text-slate-500">
              <tr>
                <th scope="col" className="px-5 py-3 font-medium">Asset</th>
                <th scope="col" className="px-4 py-3 font-medium">Type</th>
                <th scope="col" className="px-4 py-3 font-medium">Environment</th>
                <th scope="col" className="px-4 py-3 font-medium">Criticality</th>
                <th scope="col" className="px-4 py-3 font-medium">Status</th>
                <th scope="col" className="px-4 py-3 font-medium">Source / updated</th>
                {canManageAssets && <th scope="col" className="px-4 py-3 font-medium">Action</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.05]">
              {filteredAssets.map((asset) => (
                <tr key={asset.id} className="text-slate-300">
                  <td className="px-5 py-4">
                    <p className="font-medium text-white">{asset.name}</p>
                    {asset.external_id && <p className="mt-1 text-[10px] text-slate-600">{asset.external_id}</p>}
                  </td>
                  <td className="px-4 py-4">{humanize(asset.asset_type)}</td>
                  <td className="px-4 py-4">{humanize(asset.environment)}</td>
                  <td className="px-4 py-4"><span className={'rounded-full border px-2 py-1 text-[10px] ' + criticalityClass(asset.criticality)}>{humanize(asset.criticality)}</span></td>
                  <td className="px-4 py-4"><span className={asset.status === 'active' ? 'text-emerald-200' : 'text-slate-500'}>{humanize(asset.status)}</span></td>
                  <td className="px-4 py-4"><p>{humanize(asset.source)}</p><p className="mt-1 text-[10px] text-slate-600">{dateLabel(asset.updated_at)}</p></td>
                  {canManageAssets && (
                    <td className="px-4 py-4">
                      <button type="button" disabled={busyAssetId === asset.id} onClick={() => void changeAssetStatus(asset)} aria-label={(asset.status === 'active' ? 'Archive ' : 'Restore ') + asset.name} className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] px-2.5 py-2 text-[10px] text-slate-300 hover:border-cyan-200/20 disabled:opacity-50">
                        {asset.status === 'active' ? <Archive size={13} aria-hidden="true" /> : <ArchiveRestore size={13} aria-hidden="true" />}
                        {busyAssetId === asset.id ? 'Saving…' : asset.status === 'active' ? 'Archive' : 'Restore'}
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filteredAssets.length === 0 && (
          <div className="px-5 py-12 text-center">
            <Boxes size={23} className="mx-auto text-slate-600" aria-hidden="true" />
            <h3 className="mt-3 text-sm font-medium text-slate-300">{assets.length === 0 ? 'No assets on this page' : 'No matching assets'}</h3>
            <p className="mt-1 text-xs text-slate-500">{assets.length === 0 ? 'Register an asset or connect an approved discovery source.' : 'Adjust the search or filters to see more records.'}</p>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-white/[0.06] px-5 py-4">
          <button type="button" disabled={offset === 0 || loading} onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))} className="inline-flex items-center gap-1 rounded-lg border border-white/[0.08] px-3 py-2 text-xs text-slate-300 disabled:cursor-not-allowed disabled:opacity-40">
            <ChevronLeft size={14} aria-hidden="true" /> Previous
          </button>
          <span className="text-[10px] text-slate-600">50 records per page</span>
          <button type="button" disabled={assets.length < PAGE_SIZE || loading} onClick={() => setOffset((value) => value + PAGE_SIZE)} className="inline-flex items-center gap-1 rounded-lg border border-white/[0.08] px-3 py-2 text-xs text-slate-300 disabled:cursor-not-allowed disabled:opacity-40">
            Next <ChevronRight size={14} aria-hidden="true" />
          </button>
        </div>
      </div>
    </section>
  );
}
