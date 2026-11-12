import { useState } from 'react';
import { Activity, ArrowRight, BrainCircuit, CloudOff, Database, Fingerprint, PlugZap, Radar, Server, ShieldAlert, ShieldCheck } from 'lucide-react';
import { MetricCard } from './components/MetricCard';
import { Sidebar } from './components/Sidebar';
import { navigationItems } from './data/navigation.js';
import { platformReadiness } from './data/platformReadiness';
import { OrganizationPage } from './pages/OrganizationPage';

type SectionId = (typeof navigationItems)[number]['id'];

const metrics = [
  { label: 'Alerts today', value: '—', hint: 'Awaiting an authorized event source', icon: ShieldAlert, accent: 'amber' as const },
  { label: 'Open investigations', value: '—', hint: 'Case management is not connected', icon: Fingerprint, accent: 'violet' as const },
  { label: 'Agents available', value: '0', hint: 'Agent runtime is not configured', icon: BrainCircuit, accent: 'cyan' as const },
  { label: 'Connected tools', value: '0', hint: 'No security integrations are enabled', icon: PlugZap, accent: 'green' as const },
];

const readinessIcons = {
  api: Server,
  tenant: ShieldCheck,
  ai: BrainCircuit,
  memory: Database,
} as const;

const readinessStyles = {
  implemented: 'text-cyan-200',
  verified: 'text-emerald-200',
  unconfigured: 'text-amber-200',
  pending: 'text-slate-500',
} as const;

export default function App() {
  const [active, setActive] = useState<SectionId>('overview');
  const current = navigationItems.find((item) => item.id === active) ?? navigationItems[0];

  return (
    <div className="min-h-screen bg-[#090d14] text-slate-100">
      <div className="flex min-h-screen">
        <Sidebar activeSection={active} onNavigate={setActive} />
        <main className="min-w-0 flex-1">
          <header className="border-b border-white/[0.07] bg-[#0b1018] px-5 py-5 sm:px-8 lg:px-10">
            <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-4">
              <div>
                <p className="text-[11px] uppercase tracking-[0.17em] text-slate-500">AEGIS / {current.label}</p>
                <h1 className="mt-2 text-2xl font-semibold text-white">{active === 'overview' ? 'Security overview' : current.label}</h1>
                <p className="mt-1 hidden text-sm text-slate-500 sm:block">{current.description}</p>
              </div>
              <span className="inline-flex items-center gap-2 rounded-full border border-amber-300/15 bg-amber-300/[0.07] px-3 py-2 text-[11px] text-amber-200">
                <CloudOff size={13} aria-hidden="true" /> Preview mode
              </span>
            </div>
            <nav aria-label="Mobile navigation" className="mt-5 flex gap-2 overflow-x-auto lg:hidden">
              {navigationItems.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActive(item.id)}
                  aria-current={active === item.id ? 'page' : undefined}
                  className={active === item.id
                    ? 'shrink-0 rounded-full border border-cyan-200/20 bg-cyan-300/10 px-3 py-2 text-xs text-cyan-200'
                    : 'shrink-0 rounded-full border border-white/[0.07] px-3 py-2 text-xs text-slate-400'}
                >
                  {item.label}
                </button>
              ))}
            </nav>
          </header>

          <div className="surface-grid mx-auto max-w-[1500px] px-5 py-7 sm:px-8 lg:px-10">
            {active === 'overview' ? (
              <>
                <section className="rounded-2xl border border-cyan-200/[0.12] bg-gradient-to-br from-[#12212b] to-[#111522] p-6">
                  <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-center">
                    <div className="max-w-2xl">
                      <span className="inline-flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-200">
                        <ShieldCheck size={13} aria-hidden="true" /> Defensive workspace
                      </span>
                      <h2 className="mt-3 text-xl font-semibold text-white">Your security workspace is taking shape.</h2>
                      <p className="mt-2 text-sm leading-6 text-slate-400">The interface foundation is ready for customer workflows and approved integrations. No live telemetry or active security operations are connected in this preview.</p>
                    </div>
                    <div className="flex items-center gap-3 rounded-xl border border-white/[0.07] bg-black/15 px-4 py-3">
                      <Radar size={19} className="text-amber-200" aria-hidden="true" />
                      <div><p className="text-xs text-slate-300">Telemetry status</p><p className="text-xs text-amber-200">Not connected</p></div>
                    </div>
                  </div>
                </section>

                <section aria-label="Security metrics" className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  {metrics.map((metric) => <MetricCard key={metric.label} {...metric} />)}
                </section>

                <section className="mt-6 grid gap-5 xl:grid-cols-[1.55fr_0.9fr]">
                  <article className="rounded-2xl border border-white/[0.07] bg-[#101722] p-6">
                    <div className="flex items-center gap-2"><Activity size={16} className="text-cyan-300" aria-hidden="true" /><h3 className="text-sm font-semibold">Activity stream</h3></div>
                    <p className="mt-1 text-xs text-slate-500">Security events and analyst actions</p>
                    <div className="mt-7 flex min-h-52 flex-col items-center justify-center rounded-xl border border-dashed border-white/[0.09] px-5 text-center">
                      <Radar size={24} className="text-slate-500" aria-hidden="true" />
                      <h4 className="mt-4 text-sm font-medium text-slate-300">Nothing to review yet</h4>
                      <p className="mt-1 max-w-sm text-xs leading-5 text-slate-500">Activity appears after an approved event source is connected and the API is available.</p>
                      <button type="button" onClick={() => setActive('integrations')} className="mt-4 inline-flex items-center gap-2 text-xs font-medium text-cyan-200">View integrations <ArrowRight size={13} /></button>
                    </div>
                  </article>

                  <article className="rounded-2xl border border-white/[0.07] bg-[#101722] p-6">
                    <div className="flex items-center gap-2"><ShieldCheck size={16} className="text-emerald-300" aria-hidden="true" /><h3 className="text-sm font-semibold">Platform readiness</h3></div>
                    <p className="mt-1 text-xs text-slate-500">Repository implementation and CI evidence, not live service health</p>
                    <div className="mt-5 divide-y divide-white/[0.06]">
                      {platformReadiness.map((item) => {
                        const Icon = readinessIcons[item.id];
                        return (
                          <div key={item.id} className="flex items-center gap-3 py-3">
                            <Icon size={17} className="text-slate-400" aria-hidden="true" />
                            <div className="min-w-0 flex-1">
                              <p className="text-xs text-slate-300">{item.label}</p>
                              <p className="text-[11px] leading-5 text-slate-600">{item.detail}</p>
                            </div>
                            <span className={`shrink-0 text-[10px] ${readinessStyles[item.state]}`}>{item.status}</span>
                          </div>
                        );
                      })}
                    </div>
                  </article>
                </section>

                <section className="mt-5 flex items-start gap-3 rounded-2xl border border-white/[0.07] bg-[#0e141e] p-5">
                  <span className="grid size-7 shrink-0 place-items-center rounded-full border border-white/[0.08] text-slate-500">?</span>
                  <div><h3 className="text-xs font-semibold text-slate-300">Safety comes before automation</h3><p className="mt-1 text-xs leading-5 text-slate-500">Active operations require an authorized scope, least-privilege access, auditable execution, and human approval for consequential actions.</p></div>
                </section>
              </>
            ) : active === 'organization' ? (
              <OrganizationPage />
            ) : (
              <section className="mx-auto flex min-h-[420px] max-w-3xl flex-col items-center justify-center rounded-2xl border border-white/[0.07] bg-[#101722] p-8 text-center">
                <CloudOff size={28} className="text-cyan-200" aria-hidden="true" />
                <p className="mt-4 text-[10px] font-semibold uppercase tracking-[0.15em] text-amber-200">Module not connected</p>
                <h2 className="mt-3 text-xl font-semibold text-white">{current.label} is not configured yet</h2>
                <p className="mt-2 max-w-lg text-sm leading-6 text-slate-500">{current.description} This UI placeholder remains inactive until its service boundary, permissions, and tests are implemented.</p>
                <button type="button" onClick={() => setActive('overview')} className="mt-6 inline-flex items-center gap-2 rounded-xl border border-cyan-200/15 px-4 py-2.5 text-xs text-cyan-100">Return to overview <ArrowRight size={14} /></button>
              </section>
            )}

            <footer className="mt-8 flex flex-col gap-2 border-t border-white/[0.06] pt-5 text-[10px] text-slate-600 sm:flex-row sm:justify-between">
              <p>AEGIS · Defensive security workspace</p>
              <p>Preview only · No live security actions are available</p>
            </footer>
          </div>
        </main>
      </div>
    </div>
  );
}
