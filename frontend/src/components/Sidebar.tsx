import {
  Activity,
  Bot,
  BrainCircuit,
  LayoutDashboard,
  PlugZap,
  ScanSearch,
  ScrollText,
  Server,
  ShieldCheck,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { navigationItems } from '../data/navigation.js';

type SectionId = (typeof navigationItems)[number]['id'];

interface SidebarProps {
  activeSection: SectionId;
  onNavigate: (section: SectionId) => void;
}

const sectionIcons: Record<SectionId, LucideIcon> = {
  overview: LayoutDashboard,
  assets: Server,
  investigations: ScanSearch,
  agents: Bot,
  integrations: PlugZap,
  memory: BrainCircuit,
  audit: ScrollText,
};

export function Sidebar({ activeSection, onNavigate }: SidebarProps) {
  return (
    <aside className="hidden w-[258px] shrink-0 flex-col border-r border-white/[0.07] bg-[#0b1018] px-4 py-5 lg:flex">
      <div className="flex items-center gap-3 px-2">
        <span className="grid size-10 place-items-center rounded-xl bg-cyan-300/10 text-cyan-300 ring-1 ring-cyan-200/15">
          <ShieldCheck size={23} strokeWidth={1.8} aria-hidden="true" />
        </span>
        <div>
          <p className="text-[15px] font-semibold tracking-[0.22em] text-white">AEGIS</p>
          <p className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.18em] text-slate-500">Security workspace</p>
        </div>
      </div>

      <div className="mt-10 px-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">Workspace</p>
      </div>
      <nav aria-label="Primary navigation" className="mt-3 flex flex-col gap-1">
        {navigationItems.map((item) => {
          const Icon = sectionIcons[item.id];
          const active = activeSection === item.id;

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onNavigate(item.id)}
              aria-current={active ? 'page' : undefined}
              className={`group flex items-center gap-3 rounded-xl px-3 py-3 text-left text-sm transition-colors ${
                active
                  ? 'bg-cyan-300/[0.10] font-medium text-cyan-200 ring-1 ring-inset ring-cyan-200/[0.12]'
                  : 'text-slate-400 hover:bg-white/[0.04] hover:text-slate-100'
              }`}
            >
              <Icon size={17} strokeWidth={1.8} className={active ? 'text-cyan-300' : 'text-slate-500 group-hover:text-slate-300'} aria-hidden="true" />
              <span>{item.label}</span>
              {item.id === 'audit' && <span className="ml-auto size-1.5 rounded-full bg-slate-700" />}
            </button>
          );
        })}
      </nav>

      <div className="mt-auto rounded-2xl border border-white/[0.07] bg-[#101722] p-4">
        <div className="flex items-center gap-2 text-xs font-medium text-slate-300">
          <Activity size={14} className="text-amber-300" aria-hidden="true" />
          Local preview
        </div>
        <p className="mt-2 text-xs leading-5 text-slate-500">
          Services and security connectors are not configured yet.
        </p>
        <div className="mt-4 h-1 overflow-hidden rounded-full bg-slate-800">
          <div className="h-full w-1/5 rounded-full bg-cyan-300/70" />
        </div>
        <p className="mt-2 text-[10px] uppercase tracking-[0.12em] text-slate-600">Foundation stage</p>
      </div>
    </aside>
  );
}
