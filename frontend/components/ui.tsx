import { ArrowRight, BookMarked, Check, ChevronRight, Clock3, FileText, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Link from "next/link";

export function Eyebrow({ children }: { children: React.ReactNode }) {
  return <div className="motion-ink text-xs font-bold uppercase tracking-[0.24em] text-[var(--accent)]">{children}</div>;
}

export function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: React.ReactNode }) {
  return (
    <section className="motion-panel relative overflow-hidden rounded-[14px] border border-[var(--line)] bg-[rgba(255,253,247,0.82)] p-5 shadow-[0_30px_100px_rgba(18,35,59,0.08)] backdrop-blur sm:p-7">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[var(--cyan)] to-transparent opacity-70" />
      <div className="grid gap-6 lg:grid-cols-[1fr_auto] lg:items-end">
        <div className="max-w-3xl">
          <Eyebrow>{eyebrow}</Eyebrow>
          <h1 className="mt-3 max-w-4xl text-3xl font-semibold leading-[1.04] text-[var(--navy)] sm:text-5xl">{title}</h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-[var(--muted)]">{description}</p>
        </div>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
    </section>
  );
}

export function Surface({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`motion-panel rounded-[14px] border border-[var(--line)] bg-[rgba(255,253,247,0.78)] shadow-[0_22px_80px_rgba(18,35,59,0.08)] backdrop-blur ${className}`}>{children}</section>;
}

export function CommandButton({ href, children, icon: Icon = ArrowRight }: { href: string; children: React.ReactNode; icon?: LucideIcon }) {
  return (
    <Link href={href} className="command-button inline-flex h-11 items-center gap-2 rounded-[10px] bg-[var(--navy)] px-4 text-sm font-semibold text-white shadow-[0_16px_45px_rgba(18,35,59,0.22)] transition focus:outline-none focus:ring-2 focus:ring-[var(--cyan)]/45">
      {children}
      <Icon size={16} aria-hidden />
    </Link>
  );
}

export function GhostButton({ href, children, icon: Icon = ChevronRight }: { href: string; children: React.ReactNode; icon?: LucideIcon }) {
  return (
    <Link href={href} className="ghost-button inline-flex h-10 items-center gap-2 rounded-[10px] border border-[var(--line)] bg-[rgba(255,253,247,0.78)] px-3 text-sm font-semibold text-[var(--navy)] shadow-[0_10px_30px_rgba(18,35,59,0.06)] transition">
      {children}
      <Icon size={15} aria-hidden />
    </Link>
  );
}

export function LibraryHero({ title, kicker, children }: { title: string; kicker: string; children?: React.ReactNode }) {
  return (
    <section className="lamp-hero hero-parallax motion-panel relative min-h-[520px] overflow-hidden rounded-[16px] border border-[rgba(255,255,255,0.12)] bg-[var(--midnight)] shadow-[0_32px_140px_rgba(18,35,59,0.28)]">
      <div className="lamp-aura" />
      <div className="lamp-beam lamp-beam-left" />
      <div className="lamp-beam lamp-beam-right" />
      <div className="lamp-line" />
      <div className="hero-grid" />
      <div className="relative z-10 flex min-h-[520px] flex-col justify-end p-6 sm:p-10 lg:p-12">
        <div className="max-w-3xl">
          <Eyebrow>{kicker}</Eyebrow>
          <h1 className="mt-4 text-4xl font-semibold leading-[0.98] text-white sm:text-6xl lg:text-7xl">{title}</h1>
          {children ? <div className="mt-6 max-w-2xl text-lg leading-8 text-[rgba(248,251,252,0.74)]">{children}</div> : null}
        </div>
      </div>
    </section>
  );
}

export function MetricRail({ items }: { items: Array<{ label: string; value: string; detail: string }> }) {
  return (
    <div className="grid gap-3 md:grid-cols-3">
      {items.map((item) => (
        <div key={item.label} className="motion-stat rounded-[14px] border border-[var(--line)] bg-[rgba(255,253,247,0.78)] p-5 shadow-[0_18px_54px_rgba(18,35,59,0.08)]">
          <div className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--accent)]">{item.label}</div>
          <div className="mt-3 text-3xl font-semibold text-[var(--navy)]">{item.value}</div>
          <div className="mt-2 text-sm leading-6 text-[var(--muted)]">{item.detail}</div>
        </div>
      ))}
    </div>
  );
}

export function LibraryScene() {
  return (
    <LibraryHero kicker="Your study sanctuary" title="Focused learning space">
      A calm, distraction-free environment designed for serious exam preparation.
    </LibraryHero>
  );
}

export function Timeline({ items }: { items: Array<{ time?: string; title: string; detail: string }> }) {
  return (
    <div className="divide-y divide-[var(--line)]">
      {items.map((item) => (
        <div key={item.title} className="motion-ink grid gap-3 py-4 sm:grid-cols-[84px_1fr]">
          <div className="flex items-center gap-2 text-sm font-semibold text-[var(--accent)]"><Clock3 size={15} aria-hidden />{item.time ?? "Next"}</div>
          <div>
            <div className="font-semibold text-[var(--navy)]">{item.title}</div>
            <div className="mt-1 text-sm leading-6 text-[var(--muted)]">{item.detail}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function IntelligenceBadge({ label }: { label: string }) {
  return <span className="inline-flex items-center gap-1 rounded-full border border-[var(--cyan)]/30 bg-[var(--cyan-soft)] px-3 py-1 text-xs font-bold text-[var(--emerald)]"><Sparkles size={13} aria-hidden />{label}</span>;
}

export function ProgressShelf({ title, items }: { title: string; items: Array<{ label: string; value: number; tone?: string }> }) {
  return (
    <Surface className="p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-[var(--navy)]">{title}</h2>
        <BookMarked size={18} className="text-[var(--accent)]" aria-hidden />
      </div>
      <div className="mt-7 flex h-44 items-end gap-2 border-b-[10px] border-[rgba(18,35,59,0.16)] px-2 pb-1 shadow-[inset_0_-18px_22px_rgba(18,35,59,0.06)]">
        {items.map((item, index) => (
          <div key={item.label} className="motion-book group relative flex flex-1 justify-center">
            <div className="w-full max-w-[54px] rounded-t-[5px] border border-white/40 shadow-[10px_0_24px_rgba(18,35,59,0.12)] transition group-hover:-translate-y-1" style={{ height: `${48 + item.value}px`, background: item.tone ?? ["#172a46", "#15766a", "#c6a45f", "#87a5a1", "#4b5563"][index % 5] }} />
            <div className="absolute -bottom-12 w-24 text-center text-xs text-[var(--muted)]">{item.label}</div>
          </div>
        ))}
      </div>
    </Surface>
  );
}

export function Workflow({ steps }: { steps: Array<{ icon: LucideIcon; title: string; detail: string; state?: string }> }) {
  return (
    <div className="grid gap-3">
      {steps.map((step, index) => (
        <div key={step.title} className="motion-panel grid grid-cols-[42px_1fr_auto] items-center gap-4 rounded-[12px] border border-[var(--line)] bg-[rgba(255,253,247,0.62)] p-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-[var(--cyan-soft)] text-[var(--emerald)]"><step.icon size={18} aria-hidden /></div>
          <div>
            <div className="font-semibold text-[var(--navy)]">{step.title}</div>
            <div className="text-sm leading-6 text-[var(--muted)]">{step.detail}</div>
          </div>
          <div className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--accent)]">{step.state ?? `${index + 1}`}</div>
        </div>
      ))}
    </div>
  );
}

export function PaperStrip({ title, meta, href = "/reader/demo" }: { title: string; meta: string; href?: string }) {
  return (
    <Link href={href} className="motion-panel group grid grid-cols-[46px_1fr_auto] items-center gap-4 rounded-[12px] border border-[var(--line)] bg-[rgba(255,253,247,0.62)] p-3 transition hover:-translate-y-0.5 hover:border-[var(--cyan)]/50 hover:bg-white">
      <div className="flex h-11 w-11 items-center justify-center rounded-[10px] bg-[var(--cyan-soft)] text-[var(--emerald)]"><FileText size={18} aria-hidden /></div>
      <div>
        <div className="font-semibold text-[var(--navy)]">{title}</div>
        <div className="text-sm leading-6 text-[var(--muted)]">{meta}</div>
      </div>
      <ChevronRight size={17} className="text-[var(--accent)] transition group-hover:translate-x-1" aria-hidden />
    </Link>
  );
}

export function InsightList({ items }: { items: string[] }) {
  return (
    <div className="divide-y divide-[var(--line)]">
      {items.map((item) => (
        <div key={item} className="motion-ink flex items-start gap-3 py-3 text-sm leading-6 text-[var(--muted)]">
          <span className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--cyan-soft)] text-[var(--emerald)]"><Check size={13} aria-hidden /></span>
          <span>{item}</span>
        </div>
      ))}
    </div>
  );
}

export const StudyInstrument = MetricRail;
export const RitualList = Timeline;
export const SignalBadge = IntelligenceBadge;
export const ShelfMeter = ProgressShelf;
export const StudioSteps = Workflow;
