import { useState } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ChevronUp, CircleCheck, Clock, Layers, Shield, Target, TrendingUp } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type DemoPhase = {
  no: number;
  status: "completed" | "stopped" | "active";
  option: string;
  side: "BUY" | "SELL";
  lots: number;
  quantity: number;
  mtm: number;
  entry: number;
  optionEntry: number;
  stoploss: number;
  duration: string;
  time: string;
  targetCount: number;
  targets: Array<{ label: string; price: number; state: "hit" | "pending" | "skipped" }>;
};

const DEMO_PHASES: DemoPhase[] = [
  {
    no: 3,
    status: "completed",
    option: "NIFTY21JUL2623950PE",
    side: "BUY",
    lots: 4,
    quantity: 260,
    mtm: 26,
    entry: 24020.1,
    optionEntry: 151.1,
    stoploss: 24041.07,
    duration: "36s",
    time: "15:17:31 → 15:18:08",
    targetCount: 1,
    targets: [
      { label: "T1", price: 24011, state: "pending" },
    ],
  },
  {
    no: 2,
    status: "completed",
    option: "NIFTY21JUL2624000CE",
    side: "BUY",
    lots: 4,
    quantity: 260,
    mtm: 98.5,
    entry: 24054.2,
    optionEntry: 126.4,
    stoploss: 24024.2,
    duration: "5m 12s",
    time: "14:41:04 → 14:46:16",
    targetCount: 2,
    targets: [
      { label: "T1", price: 24064.2, state: "hit" },
      { label: "T2", price: 24074.2, state: "hit" },
      { label: "T3", price: 24084.2, state: "pending" },
      { label: "T4", price: 24094.2, state: "pending" },
    ],
  },
  {
    no: 1,
    status: "stopped",
    option: "NIFTY21JUL2624050PE",
    side: "SELL",
    lots: 4,
    quantity: 260,
    mtm: 77,
    entry: 24089.2,
    optionEntry: 106.8,
    stoploss: 24119.2,
    duration: "8m 41s",
    time: "13:32:37 → 13:41:18",
    targetCount: 0,
    targets: [
      { label: "T1", price: 24079.2, state: "skipped" },
      { label: "T2", price: 24069.2, state: "skipped" },
      { label: "T3", price: 24059.2, state: "skipped" },
      { label: "T4", price: 24049.2, state: "skipped" },
    ],
  },
];

function money(value: number) {
  return `Rs. ${value.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function MiniMetric({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "good" | "bad" }) {
  return (
    <div className="fr-dark-surface rounded-lg border border-border/60 bg-background/40 p-2.5">
      <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={cn("mt-1 text-sm font-semibold tabular-nums", tone === "good" && "text-emerald-500", tone === "bad" && "text-red-500")}>{value}</p>
      {sub ? <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{sub}</p> : null}
    </div>
  );
}

function statusStyle(status: DemoPhase["status"]) {
  if (status === "completed") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-500";
  if (status === "stopped") return "border-red-500/30 bg-red-500/10 text-red-400";
  return "border-sky-500/30 bg-sky-500/10 text-sky-400";
}

function PhasePanel({ phase, open, onToggle }: { phase: DemoPhase; open: boolean; onToggle: () => void }) {
  const hitTargets = phase.targets.filter((target) => target.state === "hit").length;
  return (
    <article className="relative rounded-xl border border-border/70 bg-card/50 p-3 shadow-sm">
      <span className={cn("absolute -left-1.5 top-5 h-3 w-3 rounded-full border-2 border-background", phase.status === "stopped" ? "bg-red-500" : "bg-emerald-500")} />
      <button type="button" onClick={onToggle} className="flex w-full items-start justify-between gap-3 text-left">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1 text-sm font-bold"><Layers className="h-3.5 w-3.5" /> Phase {phase.no}</span>
            <span className={cn("rounded-md border px-1.5 py-0.5 text-[11px] font-semibold capitalize", statusStyle(phase.status))}>{phase.status}</span>
          </div>
          <p className="mt-1 truncate text-xs text-muted-foreground">{phase.side} {phase.option} · {phase.lots} lots · {phase.quantity} qty</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <div className="text-right">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Phase MTM</p>
            <p className="text-sm font-bold tabular-nums text-emerald-500">{money(phase.mtm)}</p>
          </div>
          {open ? <ChevronUp className="mt-1 h-4 w-4 text-muted-foreground" /> : <ChevronDown className="mt-1 h-4 w-4 text-muted-foreground" />}
        </div>
      </button>

      {open ? (
        <div className="mt-3 space-y-3 border-t border-border/60 pt-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <MiniMetric label="Entry" value={phase.entry.toLocaleString("en-IN", { minimumFractionDigits: 2 })} sub={`Option ${money(phase.optionEntry)}`} />
            <MiniMetric label="Stop-loss" value={phase.stoploss.toLocaleString("en-IN", { minimumFractionDigits: 2 })} sub={phase.status === "stopped" ? "Hit" : "Manual"} tone={phase.status === "stopped" ? "bad" : undefined} />
            <MiniMetric label="Targets" value={`${hitTargets}/${phase.targets.length}`} sub={phase.status === "stopped" ? "Stopped before target" : `${phase.targetCount} target exits`} />
            <MiniMetric label="Duration" value={phase.duration} sub={phase.time} />
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {phase.targets.map((target) => (
              <div key={target.label} className={cn("rounded-lg border p-2", target.state === "hit" ? "border-emerald-500/30 bg-emerald-500/10" : target.state === "skipped" ? "border-border/60 bg-muted/20 opacity-70" : "border-border/60 bg-background/35")}>
                <div className="flex items-center justify-between gap-1">
                  <span className="text-xs font-semibold">{target.label}</span>
                  {target.state === "hit" ? <CircleCheck className="h-3.5 w-3.5 text-emerald-500" /> : null}
                </div>
                <p className="mt-1 text-sm font-semibold tabular-nums">{target.price.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</p>
                <p className="text-[10px] capitalize text-muted-foreground">{target.state}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </article>
  );
}

export default function FuturesRiskCardDemo() {
  const [openPhases, setOpenPhases] = useState<number[]>([3]);
  const allOpen = openPhases.length === DEMO_PHASES.length;
  const togglePhase = (phaseNo: number) => setOpenPhases((current) => current.includes(phaseNo) ? current.filter((item) => item !== phaseNo) : [...current, phaseNo]);

  return (
    <div className="fr-grid-bg -m-2 min-h-full rounded-2xl px-2 pb-4 pt-1 md:-m-4 md:px-4 md:pb-6 md:pt-2">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">All-phases card demo</h1>
            <span className="rounded-md border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-xs font-semibold text-sky-400">Demo only</span>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">One instrument card showing the current phase and every earlier phase in its own expandable timeline.</p>
        </div>
        <Link to="/tools/futures-risk" className={cn(buttonVariants({ variant: "outline" }), "shrink-0")}>Back to Positions</Link>
      </header>

      <main className="mt-5 max-w-3xl">
        <section className="fr-glass fr-dark-surface rounded-2xl border border-border/70 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-2xl font-bold tracking-tight">NIFTY</h2>
                <span className="rounded-md bg-foreground/10 px-1.5 py-0.5 text-xs font-semibold text-muted-foreground">Completed</span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">Tue, 14 Jul 2026 · 3 phases · Sandbox</p>
            </div>
            <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-right">
              <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Overall MTM</p>
              <p className="text-lg font-bold tabular-nums text-emerald-500">Rs. 201.50</p>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <MiniMetric label="Booked P&L" value="Rs. 201.50" tone="good" />
            <MiniMetric label="Targets" value="3/9" sub="Across all phases" />
            <MiniMetric label="Phase count" value="3" sub="0 active" />
            <MiniMetric label="Net quantity" value="780" sub="All phases exited" />
          </div>

          <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-4">
            <div className="flex items-center gap-2 text-sm font-semibold"><Target className="h-4 w-4 text-primary" /> All phases <span className="rounded-full bg-foreground/10 px-2 py-0.5 text-xs text-muted-foreground">{DEMO_PHASES.length}</span></div>
            <button type="button" onClick={() => setOpenPhases(allOpen ? [] : DEMO_PHASES.map((phase) => phase.no))} className="rounded-lg border border-border/70 px-2.5 py-1.5 text-xs font-semibold text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground">
              {allOpen ? "Collapse all" : "Expand all"}
            </button>
          </div>

          <div className="relative mt-3 space-y-3 border-l border-border/70 pl-4">
            {DEMO_PHASES.map((phase) => <PhasePanel key={phase.no} phase={phase} open={openPhases.includes(phase.no)} onToggle={() => togglePhase(phase.no)} />)}
          </div>
        </section>

        <aside className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="fr-glass rounded-xl border border-border/60 p-3 text-sm"><TrendingUp className="mb-2 h-4 w-4 text-emerald-500" /><p className="font-semibold">Phase visibility</p><p className="mt-1 text-xs text-muted-foreground">Every phase stays in the primary card, rather than a separate modal.</p></div>
          <div className="fr-glass rounded-xl border border-border/60 p-3 text-sm"><Shield className="mb-2 h-4 w-4 text-sky-400" /><p className="font-semibold">Fast scanning</p><p className="mt-1 text-xs text-muted-foreground">Collapsed rows show status, option, quantity, and MTM at a glance.</p></div>
          <div className="fr-glass rounded-xl border border-border/60 p-3 text-sm"><Clock className="mb-2 h-4 w-4 text-amber-500" /><p className="font-semibold">Details on demand</p><p className="mt-1 text-xs text-muted-foreground">Open a phase to review entry, stop-loss, targets and timing.</p></div>
        </aside>
      </main>
    </div>
  );
}
