/**
 * Symbol-grouped phase history for Futures-Risk positions.
 */
import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays, ChevronDown, ChevronUp, Clock, Layers, Shield, Target } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { listPhases } from "@/api/futuresRisk";
import { useMarketData } from "@/hooks/useMarketData";
import type { FrPhase } from "@/types/futuresRisk";
import { durationFmt, fmt, timeFmt } from "./frFormat";

export type PhaseDateFilter = "today" | "week" | "month" | "custom";

const DATE_FILTER_LABELS: Record<PhaseDateFilter, string> = {
  today: "Today",
  week: "Week",
  month: "Month",
  custom: "Custom",
};

function localDateKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function isoDateKey(iso: string | null | undefined): string {
  if (!iso) return "";
  return localDateKey(new Date(iso));
}

function displayDateLabel(dateKey: string): string {
  const [year, month, day] = dateKey.split("-").map(Number);
  if (!year || !month || !day) return dateKey;
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    weekday: "short",
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function rangeFor(filter: PhaseDateFilter, customFrom: string, customTo: string): { from: string; to: string } {
  const now = new Date();
  const to = localDateKey(now);
  if (filter === "custom") return { from: customFrom, to: customTo || customFrom };
  if (filter === "today") return { from: to, to };
  const from = new Date(now);
  from.setDate(now.getDate() - (filter === "week" ? 6 : 29));
  return { from: localDateKey(from), to };
}

export function PhaseHistoryFilterToolbar({
  filter,
  customFrom,
  customTo,
  onFilterChange,
}: {
  filter: PhaseDateFilter;
  customFrom: string;
  customTo: string;
  onFilterChange: (filter: PhaseDateFilter) => void;
}) {
  const range = rangeFor(filter, customFrom, customTo);
  return (
    <>
      <select
        aria-label="Phase history date range"
        value={filter}
        onChange={(event) => onFilterChange(event.target.value as PhaseDateFilter)}
        className="h-9 w-28 rounded-lg border border-border/70 bg-background/80 px-2 text-sm font-medium text-foreground outline-none transition-colors focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/30 dark:bg-background/70"
      >
        {(["today", "week", "month", "custom"] as PhaseDateFilter[]).map((value) => (
          <option key={value} value={value}>{DATE_FILTER_LABELS[value]}</option>
        ))}
      </select>
      <div className="flex h-9 items-center gap-1 rounded-lg border border-border/60 bg-background/45 px-2 text-xs tabular-nums text-muted-foreground">
        <CalendarDays className="h-3.5 w-3.5 shrink-0" />
        <span>{range.from}</span>
        <span>to</span>
        <span>{range.to}</span>
      </div>
    </>
  );
}

function phaseOpenPnl(p: FrPhase, liveOpt: number | undefined): number {
  if (p.status !== "active" || liveOpt === undefined || !p.entry_option_price || p.remaining_qty <= 0) return 0;
  const dir = p.side === "BUY" ? 1 : -1;
  const pnlQty = p.pnl_qty ?? p.remaining_qty;
  return (liveOpt - p.entry_option_price) * pnlQty * dir;
}

function phaseMtm(p: FrPhase, liveOpt: number | undefined): number {
  return (p.realized_pnl ?? 0) + phaseOpenPnl(p, liveOpt);
}

function targetQtyLabel(phase: FrPhase, completedTargets: number): string {
  if (phase.status === "active" || phase.status === "draft") {
    return `Remaining ${phase.remaining_qty}/${phase.total_qty} qty`;
  }
  const exitedQty = Math.max(0, phase.total_qty - phase.remaining_qty);
  if (phase.status === "stopped") return `Exited ${exitedQty}/${phase.total_qty} via SL`;
  if (phase.status === "completed" && phase.targets_total > 0 && completedTargets >= phase.targets_total) {
    return `Exited ${exitedQty}/${phase.total_qty} via targets`;
  }
  if (phase.exit_kind === "manual") return `Exited ${exitedQty}/${phase.total_qty} manually`;
  return `Exited ${exitedQty}/${phase.total_qty} qty`;
}

function Metric({
  label,
  value,
  sub,
  icon,
  valueClassName,
  subClassName,
  className,
}: {
  label: string;
  value: string;
  sub?: string;
  icon?: ReactNode;
  valueClassName?: string;
  subClassName?: string;
  className?: string;
}) {
  return (
    <div
      title={sub || undefined}
      className={cn("fr-dark-surface rounded-lg border border-border/60 bg-background/40 p-3", sub && "cursor-help", className)}
    >
      <div className="flex items-center gap-1 text-[11px] uppercase text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className={cn("mt-1.5 text-sm font-semibold tabular-nums", valueClassName)}>{value}</div>
      {sub ? <div className={cn("mt-0.5 truncate text-xs text-muted-foreground", subClassName)}>{sub}</div> : null}
    </div>
  );
}

function PreviousPhaseRow({ phase, liveOpt }: { phase: FrPhase; liveOpt: number | undefined }) {
  const mtm = phaseMtm(phase, liveOpt);
  const pnlTone = mtm >= 0 ? "text-emerald-500" : "text-red-500";
  const completedTargets = phase.targets.filter((t) => t.status === "hit").length;

  return (
    <div className="fr-dark-surface min-w-0 rounded-lg border border-border/60 bg-background/45 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 text-sm font-semibold">
            <Layers className="h-3.5 w-3.5" /> Phase {phase.phase_no}
          </span>
          <span className="rounded-md bg-foreground/10 px-1.5 py-0.5 text-xs font-semibold capitalize text-muted-foreground">
            {phase.status}
          </span>
        </div>
        <span className={cn("text-sm font-bold tabular-nums", pnlTone)}>Rs. {fmt(mtm)}</span>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
        <Metric label="Phase MTM" value={`Rs. ${fmt(mtm)}`} sub={phase.status === "active" ? "live + booked" : "booked"} valueClassName={pnlTone} />
        <Metric label="Entry" value={fmt(phase.entry_futures_price)} sub={`Option Rs. ${fmt(phase.entry_option_price)}`} />
        <Metric label="Stoploss" value={fmt(phase.sl_price)} sub={phase.sl_basis} />
        <Metric label="Targets" value={`${completedTargets}/${phase.targets_total}`} sub={targetQtyLabel(phase, completedTargets)} />
        <Metric
          label="Duration"
          value={durationFmt(phase.duration_sec)}
          sub={`${timeFmt(phase.entry_time)} -> ${phase.exit_time ? timeFmt(phase.exit_time) : "open"}`}
          className="sm:col-span-2"
        />
      </div>
    </div>
  );
}

function groupPhasesByDate(phases: FrPhase[]) {
  const map = new Map<string, FrPhase[]>();
  for (const phase of phases) {
    const key = isoDateKey(phase.entry_time);
    if (!key) continue;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(phase);
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([dateKey, items]) => ({
      dateKey,
      phases: [...items].sort((a, b) => a.phase_no - b.phase_no || String(a.entry_time).localeCompare(String(b.entry_time))),
    }));
}

function PreviousPhaseDateGroup({
  dateKey,
  phases,
  liveOptFor,
}: {
  dateKey: string;
  phases: FrPhase[];
  liveOptFor?: (phase: FrPhase) => number | undefined;
}) {
  const totalMtm = phases.reduce((sum, p) => sum + phaseMtm(p, liveOptFor?.(p)), 0);
  const bookedPnl = phases.reduce((sum, p) => sum + (p.realized_pnl ?? 0), 0);
  const targetsHit = phases.reduce((sum, p) => sum + p.targets_achieved.length, 0);
  const targetsTotal = phases.reduce((sum, p) => sum + p.targets_total, 0);
  const activeCount = phases.filter((p) => p.status === "active").length;
  const totalTone = totalMtm >= 0 ? "text-emerald-500" : "text-red-500";

  return (
    <section className="fr-dark-surface rounded-xl border border-border/70 bg-background/35 p-3">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="text-base font-semibold">{displayDateLabel(dateKey)}</h4>
          <p className="text-xs text-muted-foreground">{phases.length} phase(s) for this instrument</p>
        </div>
        <p className={cn("text-base font-bold tabular-nums", totalTone)}>Rs. {fmt(totalMtm)}</p>
      </div>

      <div className="mb-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        <Metric label="Date MTM" value={`Rs. ${fmt(totalMtm)}`} valueClassName={totalTone} />
        <Metric label="Booked P&L" value={`Rs. ${fmt(bookedPnl)}`} />
        <Metric label="Targets" value={`${targetsHit}/${targetsTotal}`} />
        <Metric label="Active" value={String(activeCount)} />
      </div>

      <details className="group">
        <summary className="fr-dark-surface fr-dark-surface-hover flex cursor-pointer list-none items-center justify-between rounded-lg border border-border/70 bg-background/35 px-3 py-2 text-sm font-semibold text-muted-foreground transition-colors hover:bg-background/55 hover:text-foreground">
          <span>View phases for this date ({phases.length})</span>
          <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
        </summary>
        <div className="mt-3 grid justify-center gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),360px))]">
          {phases.map((p) => (
            <PreviousPhaseRow key={p.trade_id} phase={p} liveOpt={liveOptFor?.(p)} />
          ))}
        </div>
      </details>
    </section>
  );
}

function PhaseCard({
  phase,
  liveOpt,
  previousPhases = [],
  liveOptFor,
  className,
  expanded = true,
  onToggle,
}: {
  phase: FrPhase;
  liveOpt: number | undefined;
  previousPhases?: FrPhase[];
  liveOptFor?: (phase: FrPhase) => number | undefined;
  className?: string;
  expanded?: boolean;
  onToggle?: () => void;
}) {
  const [showPreviousDetail, setShowPreviousDetail] = useState(false);
  const previousByDate = useMemo(() => groupPhasesByDate(previousPhases), [previousPhases]);
  const mtm = phaseMtm(phase, liveOpt);
  const pnlTone = mtm >= 0 ? "text-emerald-500" : "text-red-500";
  const statusTone =
    phase.status === "active"
      ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300"
      : phase.status === "stopped"
        ? "border-red-400/30 bg-red-400/10 text-red-300"
        : "border-sky-400/30 bg-sky-400/10 text-sky-300";
  const completedTargets = phase.targets.filter((t) => t.status === "hit").length;

  return (
    <div className={cn("fr-dark-surface rounded-xl border border-border/70 bg-background/35 p-3", className)}>
      <button
        type="button"
        onClick={onToggle}
        disabled={!onToggle}
        className={cn("flex w-full items-start justify-between gap-3 text-left", onToggle && "cursor-pointer")}
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1 text-base font-semibold">
              <Layers className="h-4 w-4" /> Phase {phase.phase_no}
            </span>
            <span className={cn("rounded-md border px-1.5 py-0.5 text-xs font-semibold capitalize", statusTone)}>
              {phase.status}
            </span>
          </div>
          <p className="mt-1 truncate font-mono text-xs text-muted-foreground">{phase.option_symbol}</p>
        </div>
        <div className="flex shrink-0 items-start gap-2">
          <div className="text-right">
            <p className="text-[11px] uppercase text-muted-foreground">Phase MTM</p>
            <p className={cn("text-base font-bold tabular-nums", pnlTone)}>Rs. {fmt(mtm)}</p>
          </div>
          {onToggle ? <span className="mt-1 rounded-md p-1 text-muted-foreground">{expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}</span> : null}
        </div>
      </button>

      <div className={cn(expanded === false && "hidden")}>
      <div className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        <Metric label="Entry" value={fmt(phase.entry_futures_price)} sub={`Option Rs. ${fmt(phase.entry_option_price)}`} valueClassName="text-sky-400" subClassName="text-[9px]" />
        <Metric label="Stoploss" value={fmt(phase.sl_price)} sub={phase.sl_basis} icon={<Shield className="h-3 w-3" />} valueClassName={phase.status === "stopped" ? "text-red-400" : "text-amber-400"} subClassName="text-[9px]" />
        <Metric label="Targets" value={`${completedTargets}/${phase.targets_total}`} sub={targetQtyLabel(phase, completedTargets)} icon={<Target className="h-3 w-3" />} valueClassName="text-emerald-400" subClassName="text-[9px]" />
        <Metric label="Duration" value={durationFmt(phase.duration_sec)} sub={`${timeFmt(phase.entry_time)} -> ${phase.exit_time ? timeFmt(phase.exit_time) : "open"}`} icon={<Clock className="h-3 w-3" />} valueClassName="text-violet-400" subClassName="text-[9px]" />
      </div>

      {phase.targets.length > 0 && (
        <div
          className={cn(
            "mt-3 grid gap-1.5",
            phase.targets.length === 1
              ? "grid-cols-1"
              : phase.targets.length === 2
                ? "grid-cols-2"
                : "grid-cols-2 sm:grid-cols-4",
          )}
        >
          {phase.targets.map((t) => (
            <div
              key={t.seq}
              className={cn(
                "rounded-md border px-3 py-2 text-xs",
                t.status === "hit"
                  ? "border-emerald-500/35 bg-emerald-500/10 text-emerald-700 dark:border-emerald-400/30 dark:bg-emerald-400/10 dark:text-emerald-300"
                  : "fr-dark-surface border-border/60 bg-background/40 text-muted-foreground",
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="font-semibold">T{t.seq}</div>
                  <div className="mt-0.5 tabular-nums">{fmt(t.trigger_price, 0)}</div>
                  <div className="mt-0.5 whitespace-nowrap text-[10px] opacity-80">{fmt(t.points, 0)} pts / {fmt(t.exit_pct, 0)}%</div>
                </div>
                <div className="shrink-0 text-right">
                  <div>{t.status}</div>
                  {t.status === "hit" ? (
                    <div className="mt-1 text-[11px] font-semibold tabular-nums">
                      Opt {t.exit_option_price ? fmt(t.exit_option_price) : "--"}
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {previousPhases.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setShowPreviousDetail(true)}
            className="fr-dark-surface fr-dark-surface-hover mt-3 flex w-full items-center justify-between gap-3 rounded-lg border border-border/70 bg-background/30 px-3 py-2.5 text-left text-sm font-semibold text-muted-foreground transition-colors hover:bg-background/55 hover:text-foreground"
          >
            <span>Earlier phases for this instrument ({previousPhases.length})</span>
            <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", showPreviousDetail && "rotate-180")} />
          </button>

          <Dialog open={showPreviousDetail} onOpenChange={setShowPreviousDetail}>
            <DialogContent className="fr-dark-dialog max-h-[90vh] w-[calc(100vw-1rem)] overflow-hidden p-0 sm:max-w-[min(980px,calc(100vw-2rem))]">
              <div className="scrollbar-hidden max-h-[90vh] space-y-4 overflow-y-auto overscroll-contain p-4 pr-5 sm:p-5 sm:pr-6">
                <DialogHeader>
                  <DialogTitle className="text-xl font-semibold">
                    {phase.underlying} phase history
                  </DialogTitle>
                  <DialogDescription>
                    Earlier phases grouped by trading date. Each date shows instrument MTM, booked P&L, targets, and phase details.
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-3">
                  {previousByDate.map((group) => (
                    <PreviousPhaseDateGroup
                      key={group.dateKey}
                      dateKey={group.dateKey}
                      phases={group.phases}
                      liveOptFor={liveOptFor}
                    />
                  ))}
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </>
      )}
      </div>
    </div>
  );
}

function InstrumentPhaseTimeline({
  symbol,
  phases,
  liveOptFor,
}: {
  symbol: string;
  phases: FrPhase[];
  liveOptFor: (phase: FrPhase) => number | undefined;
}) {
  const [expandedPhaseIds, setExpandedPhaseIds] = useState<number[]>(() => {
    const latest = [...phases].sort((a, b) => b.phase_no - a.phase_no || String(b.entry_time).localeCompare(String(a.entry_time)))[0];
    return latest ? [latest.trade_id] : [];
  });
  const orderedPhases = [...phases].sort((a, b) => b.phase_no - a.phase_no || String(b.entry_time).localeCompare(String(a.entry_time)));
  const latestPhase = orderedPhases[0];
  const totalMtm = phases.reduce((sum, phase) => sum + phaseMtm(phase, liveOptFor(phase)), 0);
  const realized = phases.reduce((sum, phase) => sum + (phase.realized_pnl ?? 0), 0);
  const active = phases.filter((phase) => phase.status === "active").length;
  const targetsHit = phases.reduce((sum, phase) => sum + phase.targets_achieved.length, 0);
  const targetsTotal = phases.reduce((sum, phase) => sum + phase.targets_total, 0);
  const totalQuantity = phases.reduce((sum, phase) => sum + phase.total_qty, 0);
  const totalTone = totalMtm >= 0 ? "text-emerald-500" : "text-red-500";
  const statusTone =
    latestPhase?.status === "active"
      ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300"
      : latestPhase?.status === "stopped"
        ? "border-red-400/30 bg-red-400/10 text-red-300"
        : "border-sky-400/30 bg-sky-400/10 text-sky-300";
  const allExpanded = phases.length > 0 && expandedPhaseIds.length === phases.length;
  const togglePhase = (phaseId: number) => setExpandedPhaseIds((current) => current.includes(phaseId) ? current.filter((id) => id !== phaseId) : [...current, phaseId]);

  return (
    <section className="fr-glass fr-dark-surface h-fit rounded-2xl border border-border/70 p-4">
      <div className="flex flex-nowrap items-start justify-between gap-3 max-[380px]:flex-wrap">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-2xl font-bold tracking-tight">{symbol}</h3>
            {latestPhase ? <span className={cn("rounded-md border px-1.5 py-0.5 text-xs font-semibold capitalize", statusTone)}>{latestPhase.status}</span> : null}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{phases.length} phase(s) on this trading day · {active} active</p>
        </div>
        <div className="shrink-0 rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-right">
          <p className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">Overall MTM</p>
          <p className={cn("text-lg font-bold tabular-nums", totalTone)}>Rs. {fmt(totalMtm)}</p>
        </div>
      </div>

      <aside className="mt-4 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        <Metric label="Booked P&L" value={`Rs. ${fmt(realized)}`} valueClassName={realized >= 0 ? "text-emerald-500" : "text-red-500"} className="min-h-16 bg-card/55" />
        <Metric label="Targets" value={`${targetsHit}/${targetsTotal}`} sub="Across all phases" valueClassName="text-emerald-400" className="min-h-16 bg-card/55" />
        <Metric label="Phase count" value={String(phases.length)} sub={`${active} active`} className="min-h-16 bg-card/55" />
        <Metric label="Net quantity" value={fmt(totalQuantity, 0)} sub="Across all phases" className="min-h-16 bg-card/55" />
      </aside>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-4">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Target className="h-4 w-4 text-primary" /> All phases
          <span className="rounded-full bg-foreground/10 px-2 py-0.5 text-xs text-muted-foreground">{phases.length}</span>
        </div>
        <button type="button" onClick={() => setExpandedPhaseIds(allExpanded ? [] : phases.map((phase) => phase.trade_id))} className="rounded-lg border border-border/70 px-2.5 py-1.5 text-xs font-semibold text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground">
          {allExpanded ? "Collapse all" : "Expand all"}
        </button>
      </div>

      <div className="relative mt-3 space-y-3 border-l border-border/70 pl-4">
        {orderedPhases.map((phase) => (
          <div key={phase.trade_id} className="relative">
            <span className={cn("absolute -left-[22px] top-5 h-3 w-3 rounded-full border-2 border-background", phase.status === "stopped" ? "bg-red-500" : phase.status === "active" ? "bg-sky-500" : "bg-emerald-500")} />
            <PhaseCard phase={phase} liveOpt={liveOptFor(phase)} expanded={expandedPhaseIds.includes(phase.trade_id)} onToggle={() => togglePhase(phase.trade_id)} className="bg-card/60" />
          </div>
        ))}
      </div>
    </section>
  );
}

export function PhaseHistory({
  underlying,
  mode,
  dataOverride,
  filter,
  customFrom,
  customTo,
  onCustomFromChange,
  onCustomToChange,
}: {
  underlying?: string;
  mode?: "live" | "sandbox";
  dataOverride?: FrPhase[];
  filter: PhaseDateFilter;
  customFrom: string;
  customTo: string;
  onCustomFromChange: (value: string) => void;
  onCustomToChange: (value: string) => void;
}) {
  const { data } = useQuery({
    queryKey: ["fr-phases", mode ?? "current", underlying ?? "all"],
    queryFn: () => listPhases(underlying, mode),
    refetchInterval: 8000,
    enabled: !dataOverride,
  });

  const allPhases = dataOverride ?? data ?? [];
  const range = rangeFor(filter, customFrom, customTo);
  const filtered = useMemo(() => {
    return allPhases.filter((p) => {
      const key = isoDateKey(p.entry_time);
      if (!key) return false;
      return (!range.from || key >= range.from) && (!range.to || key <= range.to);
    });
  }, [allPhases, range.from, range.to]);

  const liveSymbols = useMemo(() => {
    const seen = new Set<string>();
    const out: Array<{ symbol: string; exchange: string }> = [];
    for (const p of filtered) {
      if (p.status !== "active" || !p.option_symbol || !p.option_exchange) continue;
      const key = `${p.option_exchange}:${p.option_symbol}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ symbol: p.option_symbol, exchange: p.option_exchange });
    }
    return out;
  }, [filtered]);

  const { data: tickMap } = useMarketData({
    symbols: liveSymbols,
    mode: "LTP",
    enabled: !dataOverride && liveSymbols.length > 0,
  });

  const dayGroups = useMemo(() => {
    const byDate = new Map<string, Map<string, FrPhase[]>>();
    for (const p of filtered) {
      const dateKey = isoDateKey(p.entry_time);
      if (!dateKey) continue;
      if (!byDate.has(dateKey)) byDate.set(dateKey, new Map());
      const instrumentMap = byDate.get(dateKey)!;
      if (!instrumentMap.has(p.underlying)) instrumentMap.set(p.underlying, []);
      instrumentMap.get(p.underlying)!.push(p);
    }
    return Array.from(byDate.entries())
      .sort(([a], [b]) => b.localeCompare(a))
      .map(([dateKey, instrumentMap]) => {
        const instruments = Array.from(instrumentMap.entries())
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([symbol, phases]) => ({
            symbol,
            phases: [...phases].sort(
              (a, b) => a.phase_no - b.phase_no || String(a.entry_time).localeCompare(String(b.entry_time)),
            ),
          }));
        return { dateKey, instruments };
      });
  }, [filtered]);

  const liveOpt = (p: FrPhase): number | undefined => tickMap.get(`${p.option_exchange}:${p.option_symbol}`)?.data.ltp;

  return (
    <div className="space-y-4">
      {filter === "custom" && (
        <div className="fr-glass fr-dark-surface grid w-full gap-2 rounded-xl border border-border/70 p-3 sm:w-fit sm:grid-cols-[1fr_auto_1fr] sm:items-center">
          <input
            type="date"
            value={customFrom}
            onChange={(event) => onCustomFromChange(event.target.value)}
            className="h-9 rounded-lg border border-border/70 bg-background/80 px-3 text-sm outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/30 dark:[color-scheme:dark]"
          />
          <span className="text-center text-sm text-muted-foreground">to</span>
          <input
            type="date"
            value={customTo}
            onChange={(event) => onCustomToChange(event.target.value)}
            className="h-9 rounded-lg border border-border/70 bg-background/80 px-3 text-sm outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/30 dark:[color-scheme:dark]"
          />
        </div>
      )}

      {dayGroups.length === 0 ? (
        <p className="text-sm text-muted-foreground">No phase history for the selected date range.</p>
      ) : (
        <div className="space-y-5">
          {dayGroups.map(({ dateKey, instruments }) => (
            <section key={dateKey} className="space-y-3">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h3 className="text-lg font-bold tracking-tight">{displayDateLabel(dateKey)}</h3>
                <p className="text-sm text-muted-foreground">{instruments.length} instrument(s)</p>
              </div>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
                {instruments.map(({ symbol, phases }) => {
                  return (
                    <InstrumentPhaseTimeline key={`${dateKey}:${symbol}`} symbol={symbol} phases={phases} liveOptFor={liveOpt} />
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
