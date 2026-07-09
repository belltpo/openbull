/**
 * Symbol-grouped phase history for Futures-Risk positions.
 */
import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays, ChevronDown, Clock, Layers, Shield, Target, TrendingUp } from "lucide-react";

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

type DateFilter = "today" | "week" | "month" | "custom";

const DATE_FILTER_LABELS: Record<DateFilter, string> = {
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

function rangeFor(filter: DateFilter, customFrom: string, customTo: string): { from: string; to: string } {
  const now = new Date();
  const to = localDateKey(now);
  if (filter === "custom") return { from: customFrom, to: customTo || customFrom };
  if (filter === "today") return { from: to, to };
  const from = new Date(now);
  from.setDate(now.getDate() - (filter === "week" ? 6 : 29));
  return { from: localDateKey(from), to };
}

function phaseOpenPnl(p: FrPhase, liveOpt: number | undefined): number {
  if (p.open_pnl !== null && p.open_pnl !== undefined) return Number(p.open_pnl);
  if (p.status !== "active" || liveOpt === undefined || !p.entry_option_price || p.remaining_qty <= 0) return 0;
  const dir = p.side === "BUY" ? 1 : -1;
  return (liveOpt - p.entry_option_price) * p.remaining_qty * dir;
}

function phaseMtm(p: FrPhase, liveOpt: number | undefined): number {
  if (p.total_pnl !== null && p.total_pnl !== undefined) return Number(p.total_pnl);
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
  className,
}: {
  label: string;
  value: string;
  sub?: string;
  icon?: ReactNode;
  valueClassName?: string;
  className?: string;
}) {
  return (
    <div className={cn("fr-dark-surface rounded-lg border border-border/60 bg-background/40 p-3", className)}>
      <div className="flex items-center gap-1 text-[11px] uppercase text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className={cn("mt-1.5 text-sm font-semibold tabular-nums", valueClassName)}>{value}</div>
      {sub ? <div className="mt-0.5 truncate text-xs text-muted-foreground">{sub}</div> : null}
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
}: {
  phase: FrPhase;
  liveOpt: number | undefined;
  previousPhases?: FrPhase[];
  liveOptFor?: (phase: FrPhase) => number | undefined;
  className?: string;
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
      <div className="flex items-start justify-between gap-3">
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
        <div className="text-right">
          <p className="text-[11px] uppercase text-muted-foreground">Phase MTM</p>
          <p className={cn("text-base font-bold tabular-nums", pnlTone)}>Rs. {fmt(mtm)}</p>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2 xl:grid-cols-3">
        <Metric label="Phase MTM" value={`Rs. ${fmt(mtm)}`} sub={phase.status === "active" ? "live + booked" : "booked"} valueClassName={pnlTone} />
        <Metric label="Entry" value={fmt(phase.entry_futures_price)} sub={`Option Rs. ${fmt(phase.entry_option_price)}`} />
        <Metric label="Stoploss" value={fmt(phase.sl_price)} sub={phase.sl_basis} icon={<Shield className="h-3 w-3" />} />
        <Metric label="Targets" value={`${completedTargets}/${phase.targets_total}`} sub={targetQtyLabel(phase, completedTargets)} icon={<Target className="h-3 w-3" />} />
        <Metric label="Duration" value={durationFmt(phase.duration_sec)} sub={`${timeFmt(phase.entry_time)} -> ${phase.exit_time ? timeFmt(phase.exit_time) : "open"}`} icon={<Clock className="h-3 w-3" />} />
      </div>

      {phase.targets.length > 0 && (
        <div className="mt-3 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
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
                  <div className="mt-0.5 text-[11px] opacity-80">{fmt(t.points, 0)} pts / {fmt(t.exit_pct, 0)}%</div>
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
  );
}

export function PhaseHistory({
  underlying,
  mode,
  dataOverride,
}: {
  underlying?: string;
  mode?: "live" | "sandbox";
  dataOverride?: FrPhase[];
}) {
  const [filter, setFilter] = useState<DateFilter>("today");
  const today = localDateKey(new Date());
  const [customFrom, setCustomFrom] = useState(today);
  const [customTo, setCustomTo] = useState(today);

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
      <div className="fr-glass fr-dark-surface flex w-full flex-col gap-3 rounded-xl border border-border/70 p-3 lg:w-fit lg:min-w-[22rem]">
        <div className="grid gap-2 sm:grid-cols-[minmax(12rem,1fr)_auto] sm:items-end">
          <div className="space-y-1.5">
            <label className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Phase History Filter
            </label>
            <select
              value={filter}
              onChange={(event) => setFilter(event.target.value as DateFilter)}
              className="h-10 w-full rounded-lg border border-border/70 bg-background/80 px-3 text-sm font-semibold text-foreground outline-none transition-colors focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/30 dark:bg-background/70"
            >
              {(["today", "week", "month", "custom"] as DateFilter[]).map((f) => (
                <option key={f} value={f}>
                  {DATE_FILTER_LABELS[f]}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-1 rounded-lg border border-border/60 bg-background/45 px-3 py-2 text-xs text-muted-foreground">
            <CalendarDays className="h-4 w-4" />
            <span>{range.from}</span>
            <span>to</span>
            <span>{range.to}</span>
          </div>
        </div>
        {filter === "custom" && (
          <div className="grid gap-2 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
            <input
              type="date"
              value={customFrom}
              onChange={(e) => setCustomFrom(e.target.value)}
              className="h-10 rounded-lg border border-border/70 bg-background/80 px-3 text-sm outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/30 dark:[color-scheme:dark]"
            />
            <span className="text-center text-sm text-muted-foreground">to</span>
            <input
              type="date"
              value={customTo}
              onChange={(e) => setCustomTo(e.target.value)}
              className="h-10 rounded-lg border border-border/70 bg-background/80 px-3 text-sm outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary/30 dark:[color-scheme:dark]"
            />
          </div>
        )}
      </div>

      {dayGroups.length === 0 ? (
        <p className="text-sm text-muted-foreground">No phase history for the selected date range.</p>
      ) : (
        <div className="space-y-5">
          {dayGroups.map(({ dateKey, instruments }) => (
            <section key={dateKey} className="space-y-3">
              <div className="flex flex-wrap items-end justify-between gap-2">
                <div>
                  <h3 className="text-lg font-bold tracking-tight">{displayDateLabel(dateKey)}</h3>
                  <p className="text-sm text-muted-foreground">{instruments.length} instrument(s)</p>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
                {instruments.map(({ symbol, phases }) => {
                  const selectedInstrumentPhases = phases;
                  const latestPhase = phases[phases.length - 1];
                  const totalMtm = selectedInstrumentPhases.reduce((sum, p) => sum + phaseMtm(p, liveOpt(p)), 0);
                  const realized = selectedInstrumentPhases.reduce((sum, p) => sum + (p.realized_pnl ?? 0), 0);
                  const active = selectedInstrumentPhases.filter((p) => p.status === "active").length;
                  const targetsHit = selectedInstrumentPhases.reduce((sum, p) => sum + p.targets_achieved.length, 0);
                  const targetsTotal = selectedInstrumentPhases.reduce((sum, p) => sum + p.targets_total, 0);
                  const totalTone = totalMtm >= 0 ? "text-emerald-500" : "text-red-500";

                  return (
                    <section key={`${dateKey}:${symbol}`} className="fr-glass fr-dark-surface h-fit rounded-2xl border border-border/70 p-4">
                      <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
                        <div className="min-w-0">
                          <h3 className="text-2xl font-bold tracking-tight">{symbol}</h3>
                          <p className="mt-1 text-sm text-muted-foreground">
                            Showing latest of {selectedInstrumentPhases.length} phase(s) on this day
                          </p>
                        </div>
                      </div>

                      <aside className="mb-3 grid grid-cols-2 gap-2 text-right text-sm">
                        <Metric
                          label="Overall Instrument MTM"
                          value={`Rs. ${fmt(totalMtm)}`}
                          icon={<TrendingUp className="h-3 w-3" />}
                          valueClassName={totalTone}
                          className="min-h-16 bg-card/55"
                        />
                        <Metric label="Booked P&L" value={`Rs. ${fmt(realized)}`} className="min-h-16 bg-card/55" />
                        <Metric label="Targets" value={`${targetsHit}/${targetsTotal}`} className="min-h-16 bg-card/55" />
                        <Metric label="Active Phases" value={String(active)} className="min-h-16 bg-card/55" />
                      </aside>

                      <div className="grid min-w-0 grid-cols-1 gap-3">
                        {latestPhase && (
                          <PhaseCard
                            key={latestPhase.trade_id}
                            phase={latestPhase}
                            liveOpt={liveOpt(latestPhase)}
                            previousPhases={selectedInstrumentPhases.filter(
                              (item) => item.phase_no > 0 && item.phase_no < latestPhase.phase_no,
                            )}
                            liveOptFor={liveOpt}
                            className="bg-card/60"
                          />
                        )}
                      </div>
                    </section>
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
