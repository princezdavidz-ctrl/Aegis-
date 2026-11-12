import { useEffect, useMemo, useState } from 'react';
import { AlertCircle, Boxes, RefreshCw, Search, ShieldCheck, Server } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import {
  AssetInventoryApiError,
  createAssetInventoryClient,
  type AssetCriticality,
  type AssetRecord,
  type AssetType,
} from '../api/assets';
import type { TenantSession } from '../api/tenantSession';

interface AssetInventoryPageProps {
  /** Supplied only by a future verified OIDC browser session adapter. */
  session?: TenantSession;
  apiBaseUrl?: string;
  fetchImplementation?: typeof fetch;
}

const PAGE_SIZE = 50;
const assetTypeLabels: Record<AssetType, string> = {
  cloud_account: 'Cloud account',
  endpoint: 'Endpoint',
  server: 'Server',
  domain: 'Domain',
  repository: 'Repository',
  network: 'Network',
  application: 'Application',
  database: 'Database',
  user_identity: 'User identity',
  other: 'Other',
};
const criticalityClasses: Record<AssetCriticality, string> = {
  critical: 'border-rose-300/20 bg-rose-300/[0.08] text-rose-200',
  high: 'border-amber-300/20 bg-amber-300/[0.08] text-amber-200',
  medium: 'border-cyan-300/15 bg-cyan-300/[0.06] text-cyan-100',
  low: 'border-slate-300/15 bg-slate-300/[0.05] text-slate-300',
};

function errorMessage(error: unknown): string {
  if (error instanceof AssetInventoryApiError && error.status === 401) {
    return 'Your session is not valid. Sign in again before viewing this inventory.';
  }
  if (error instanceof AssetInventoryApiError && error.status === 403) {
    return 'Your account does not have access to the selected organization.';
  }
  return 'The asset inventory could not be loaded. Check the service connection and try again.';
}

function ConnectionState({
  title,
  description,
  icon: Icon = Boxes,
}: {
  title: string;
  description: string;
  icon?: LucideIcon;
}) {
  return (
    <section
      aria-labelledby="asset-inventory-heading"
      className="mx-auto flex min-h-[420px] max-w-3xl flex-col items-center justify-center rounded-2xl border border-white/[0.07] bg-[#101722] p-8 text-center"
    >
      <span className="grid size-12 place-items-center rounded-2xl border border-cyan-200/15 bg-cyan-300/[0.07] text-cyan-200">
        <Icon size={23} aria-hidden="true" />
      </span>
      <p className="mt-5 text-[10px] font-semibold uppercase tracking-[0.15em] text-amber-200">
        Customer asset inventory
      </p>
      <h2 id="asset-inventory-heading" className="mt-3 text-xl font-semibold text-white">{title}</h2>
      <p className="mt-2 max-w-lg text-sm leading-6 text-slate-500">{description}</p>
    </section>
  );
}

function SummaryCard({ label, value, hint }: { label: string; value: number; hint: string }) {
  return (
    <article className="rounded-xl border border-white/[0.07] bg-[#101722] p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-white">{value}</p>
      <p className="mt-1 text-[11px] text-slate-500">{hint}</p>
    </article>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value));
}

export function AssetInventoryPage({
  session,
  apiBaseUrl = '',
  fetchImplementation,
}: AssetInventoryPageProps) {
  const clientConfig = useMemo(() => {
    if (!apiBaseUrl.trim()) return { state: 'missing' as const };
    try {
      return {
        state: 'ready' as const,
        client: createAssetInventoryClient(apiBaseUrl, fetchImplementation),
      };
    } catch {
      return { state: 'invalid' as const };
    }
  }, [apiBaseUrl, fetchImplementation]);

  const [assets, setAssets] = useState<AssetRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [moreError, setMoreError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [includeArchived, setIncludeArchived] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<'all' | AssetType>('all');
  const [criticalityFilter, setCriticalityFilter] = useState<'all' | AssetCriticality>('all');

  useEffect(() => {
    if (!session || clientConfig.state !== 'ready') return;
    let active = true;
    setLoading(true);
    setError(null);
    setMoreError(null);
    setAssets([]);
    setHasMore(false);

    clientConfig.client
      .listAssets(session, { includeArchived, limit: PAGE_SIZE, offset: 0 })
      .then((result) => {
        if (active) {
          setAssets(result);
          setHasMore(result.length === PAGE_SIZE);
        }
      })
      .catch((reason: unknown) => {
        if (active) setError(errorMessage(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [session, clientConfig, includeArchived, retryCount]);

  const visibleAssets = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return assets.filter((asset) => {
      const matchesQuery = query.length === 0 ||
        [asset.name, asset.external_id ?? '', asset.asset_type, asset.environment]
          .some((value) => value.toLocaleLowerCase().includes(query));
      const matchesType = typeFilter === 'all' || asset.asset_type === typeFilter;
      const matchesCriticality =
        criticalityFilter === 'all' || asset.criticality === criticalityFilter;
      return matchesQuery && matchesType && matchesCriticality;
    });
  }, [assets, search, typeFilter, criticalityFilter]);

  async function loadMore() {
    if (!session || clientConfig.state !== 'ready' || loadingMore) return;
    setLoadingMore(true);
    setMoreError(null);
    try {
      const nextPage = await clientConfig.client.listAssets(session, {
        includeArchived,
        limit: PAGE_SIZE,
        offset: assets.length,
      });
      setAssets((current) => {
        const knownIds = new Set(current.map((asset) => asset.id));
        return [...current, ...nextPage.filter((asset) => !knownIds.has(asset.id))];
      });
      setHasMore(nextPage.length === PAGE_SIZE);
    } catch (reason) {
      setMoreError(errorMessage(reason));
    } finally {
      setLoadingMore(false);
    }
  }

  if (!session) {
    return (
      <ConnectionState
        title="Connect your organization account"
        description="Assets are shown only after trusted sign-in and a server-side membership check. Authentication is not connected in this preview, so no sample asset records are displayed."
      />
    );
  }
  if (clientConfig.state === 'missing') {
    return (
      <ConnectionState
        title="API connection is not configured"
        description="Set VITE_AEGIS_API_BASE_URL to the HTTPS API origin. Access tokens must come from a trusted runtime identity adapter and must never be stored in Vite environment variables."
        icon={AlertCircle}
      />
    );
  }
  if (clientConfig.state === 'invalid') {
    return (
      <ConnectionState
        title="API configuration is invalid"
        description="The API origin must use HTTPS. HTTP is accepted only for localhost development; URL credentials, query strings, fragments and path prefixes are not allowed."
        icon={AlertCircle}
      />
    );
  }
  if (loading) {
    return (
      <section aria-live="polite" className="rounded-2xl border border-white/[0.07] bg-[#101722] p-8">
        <p className="text-sm text-slate-300">Loading tenant asset inventory…</p>
      </section>
    );
  }
  if (error) {
    return (
      <section role="alert" className="rounded-2xl border border-amber-200/15 bg-[#171923] p-8">
        <div className="flex items-center gap-2 text-amber-200">
          <AlertCircle size={17} aria-hidden="true" />
          <h2 className="text-sm font-semibold">Asset inventory unavailable</h2>
        </div>
        <p className="mt-3 text-sm leading-6 text-slate-400">{error}</p>
        <button
          type="button"
          onClick={() => setRetryCount((count) => count + 1)}
          className="mt-5 inline-flex items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-xs text-slate-200 hover:bg-white/5"
        >
          <RefreshCw size={13} aria-hidden="true" /> Retry
        </button>
      </section>
    );
  }

  const criticalCount = assets.filter((asset) => asset.criticality === 'critical').length;
  const productionCount = assets.filter((asset) => asset.environment === 'production').length;

  return (
    <section aria-labelledby="asset-inventory-title" className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-200">Customer workspace</p>
          <h2 id="asset-inventory-title" className="mt-2 text-2xl font-semibold text-white">Asset inventory</h2>
          <p className="mt-1 text-sm text-slate-500">Tenant-scoped records from the authorized AEGIS API.</p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-cyan-300/15 bg-cyan-300/[0.06] px-3 py-2 text-[11px] text-cyan-100">
          <ShieldCheck size={13} aria-hidden="true" /> Read-only view
        </span>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <SummaryCard label="Assets loaded" value={assets.length} hint="Current pages from the API" />
        <SummaryCard label="Critical assets" value={criticalCount} hint="Marked critical by the organization" />
        <SummaryCard label="Production assets" value={productionCount} hint="Environment marked production" />
      </div>

      <article className="overflow-hidden rounded-2xl border border-white/[0.07] bg-[#101722]">
        <div className="flex flex-col justify-between gap-3 border-b border-white/[0.06] p-5 sm:flex-row sm:items-center">
          <div>
            <h3 className="text-sm font-semibold text-white">Registered assets</h3>
            <p className="mt-1 text-xs text-slate-500">Showing {visibleAssets.length} of {assets.length} loaded records.</p>
          </div>
          <label className="inline-flex items-center gap-2 text-xs text-slate-400">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(event) => setIncludeArchived(event.target.checked)}
              className="size-4 accent-cyan-300"
            />
            Include archived
          </label>
        </div>

        <div className="grid gap-3 border-b border-white/[0.06] p-5 md:grid-cols-3">
          <label className="block text-xs text-slate-400">
            Search loaded assets
            <span className="mt-2 flex items-center gap-2 rounded-lg border border-white/[0.09] bg-[#0c131d] px-3">
              <Search size={14} className="text-slate-500" aria-hidden="true" />
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Name, ID, type or environment"
                className="min-w-0 flex-1 bg-transparent py-2.5 text-sm text-slate-200 outline-none placeholder:text-slate-600"
              />
            </span>
          </label>
          <label className="block text-xs text-slate-400">
            Asset type
            <select
              value={typeFilter}
              onChange={(event) => setTypeFilter(event.target.value as 'all' | AssetType)}
              className="mt-2 w-full rounded-lg border border-white/[0.09] bg-[#0c131d] px-3 py-2.5 text-sm text-slate-200"
            >
              <option value="all">All types</option>
              {Object.entries(assetTypeLabels).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label className="block text-xs text-slate-400">
            Criticality
            <select
              value={criticalityFilter}
              onChange={(event) => setCriticalityFilter(event.target.value as 'all' | AssetCriticality)}
              className="mt-2 w-full rounded-lg border border-white/[0.09] bg-[#0c131d] px-3 py-2.5 text-sm text-slate-200"
            >
              <option value="all">All levels</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
          </label>
        </div>

        {assets.length === 0 ? (
          <div className="flex min-h-56 flex-col items-center justify-center px-6 py-10 text-center">
            <Boxes size={24} className="text-slate-500" aria-hidden="true" />
            <h4 className="mt-4 text-sm font-medium text-slate-300">No assets registered yet</h4>
            <p className="mt-1 max-w-md text-xs leading-5 text-slate-500">
              This organization has no inventory records available. Registration and editing controls will be added after the customer session and role-aware workflow are connected.
            </p>
          </div>
        ) : visibleAssets.length === 0 ? (
          <div className="px-6 py-12 text-center text-sm text-slate-500">No loaded assets match the current filters.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] border-collapse text-left">
              <caption className="sr-only">Tenant asset inventory</caption>
              <thead className="bg-[#0d141e] text-[10px] uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  <th scope="col" className="px-5 py-3 font-medium">Asset</th>
                  <th scope="col" className="px-5 py-3 font-medium">Environment</th>
                  <th scope="col" className="px-5 py-3 font-medium">Criticality</th>
                  <th scope="col" className="px-5 py-3 font-medium">Status</th>
                  <th scope="col" className="px-5 py-3 font-medium">Source</th>
                  <th scope="col" className="px-5 py-3 font-medium">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.05]">
                {visibleAssets.map((asset) => (
                  <tr key={asset.id} className="text-xs text-slate-300">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <span className="grid size-8 shrink-0 place-items-center rounded-lg border border-white/[0.07] bg-[#0d141e] text-slate-400">
                          <Server size={15} aria-hidden="true" />
                        </span>
                        <span className="min-w-0">
                          <span className="block max-w-[240px] truncate font-medium text-slate-100">{asset.name}</span>
                          <span className="mt-1 block text-[10px] text-slate-500">
                            {assetTypeLabels[asset.asset_type]} · {asset.external_id ?? 'No external ID'}
                          </span>
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-4 capitalize">{asset.environment}</td>
                    <td className="px-5 py-4">
                      <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] ${criticalityClasses[asset.criticality]}`}>
                        {asset.criticality}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span className={asset.status === 'active' ? 'text-emerald-200' : 'text-slate-500'}>{asset.status}</span>
                    </td>
                    <td className="px-5 py-4 text-slate-500">{asset.source}</td>
                    <td className="px-5 py-4 whitespace-nowrap text-slate-500">{formatDate(asset.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {moreError && <p role="alert" className="border-t border-amber-200/10 px-5 py-3 text-xs text-amber-200">{moreError}</p>}
        {hasMore && (
          <div className="flex justify-center border-t border-white/[0.06] p-4">
            <button
              type="button"
              onClick={loadMore}
              disabled={loadingMore}
              className="rounded-lg border border-white/10 px-4 py-2 text-xs text-slate-200 hover:bg-white/5 disabled:cursor-wait disabled:opacity-50"
            >
              {loadingMore ? 'Loading…' : 'Load more assets'}
            </button>
          </div>
        )}
      </article>
    </section>
  );
}
