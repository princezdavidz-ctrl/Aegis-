import type { LucideIcon } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string;
  hint: string;
  icon: LucideIcon;
  accent: 'cyan' | 'violet' | 'amber' | 'green';
}

const accentStyles: Record<MetricCardProps['accent'], string> = {
  cyan: 'bg-cyan-400/10 text-cyan-300 ring-cyan-300/15',
  violet: 'bg-violet-400/10 text-violet-300 ring-violet-300/15',
  amber: 'bg-amber-400/10 text-amber-300 ring-amber-300/15',
  green: 'bg-emerald-400/10 text-emerald-300 ring-emerald-300/15',
};

export function MetricCard({ label, value, hint, icon: Icon, accent }: MetricCardProps) {
  return (
    <article className="rounded-2xl border border-white/[0.07] bg-[#101722] p-5 shadow-[0_12px_35px_rgba(0,0,0,0.12)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-slate-400">{label}</p>
          <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-100">{value}</p>
        </div>
        <span className={`grid size-10 place-items-center rounded-xl ring-1 ${accentStyles[accent]}`}>
          <Icon size={19} strokeWidth={1.8} aria-hidden="true" />
        </span>
      </div>
      <p className="mt-4 text-xs leading-5 text-slate-500">{hint}</p>
    </article>
  );
}
