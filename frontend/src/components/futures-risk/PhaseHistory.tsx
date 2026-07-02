/**
 * Symbol-grouped phase history for Futures-Risk positions.
 */
import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays, ChevronDown, Clock, Layers, Shield, Target, TrendingUp } from "lucide-react";

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
  if (p.status !== "active" || liveOpt === undefined || !p.entry_option_price || p.remaining_qty <= 0) return 0;
  const dir = p.side === "BUY" ? 1 : -1;
  return (liveOpt - p.entry_option_price) * p.remaining_qty * dir;
}

function phaseMtm(p: FrPhase, liveOpt: number | undefined): number {
  return (p.realized_pnl ?? 0) + phaseOpenPnl(p, liveOpt);
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
        <Metric label="Targets" value={`${completedTargets}/${phase.targets_total}`} sub={`${phase.remaining_qty}/${phase.total_qty} qty`} />
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
        <Metric label="Targets" value={`${completedTargets}/${phase.targets_total}`} sub={`${phase.remaining_qty}/${phase.total_qty} qty`} icon={<Target className="h-3 w-3" />} />
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
                  ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300"
                  : "fr-dark-surface border-border/60 bg-background/40 text-muted-foreground",
              )}
            >
              <div className="flex justify-between gap-2">
                <span>T{t.seq}</span>
                <span>{t.status}</span>
              </div>
              <div className="mt-0.5 tabular-nums">{fmt(t.trigger_price, 0)}</div>
              <div className="mt-0.5 text-[11px] opacity-80">{fmt(t.points, 0)} pts / {fmt(t.exit_pct, 0)}%</div>
            </div>
          ))}
        </div>
      )}

      {previousPhases.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setShowPreviousDetail((value) => !value)}
            className="fr-dark-surface fr-dark-surface-hover mt-3 flex w-full items-center justify-between gap-3 rounded-lg border border-border/70 bg-background/30 px-3 py-2.5 text-left text-sm font-semibold text-muted-foreground transition-colors hover:bg-background/55 hover:text-foreground"
          >
            <span>Earlier phases for this instrument ({previousPhases.length})</span>
            <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", showPreviousDetail && "rotate-180")} />
          </button>

          {showPreviousDetail && (
            <div className="scrollbar-hidden mt-2 max-h-[32rem] space-y-2 overflow-y-auto rounded-xl border border-border/60 bg-background/20 p-2">
              {previousPhases.map((p) => (
                <PreviousPhaseRow key={p.trade_id} phase={p} liveOpt={liveOptFor?.(p)} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function PhaseHistory({ underlying, dataOverride }: { underlying?: string; dataOverride?: FrPhase[] }) {
  const [filter, setFilter] = useState<DateFilter>("today");
  const today = localDateKey(new Date());
  const [customFrom, setCustomFrom] = useState(today);
  const [customTo, setCustomTo] = useState(today);

  const { data } = useQuery({
    queryKey: ["fr-phases", underlying ?? "all"],
    queryFn: () => listPhases(underlying),
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

  const groups = useMemo(() => {
    const map = new Map<string, FrPhase[]>();
    for (const p of filtered) {
      if (!map.has(p.underlying)) map.set(p.underlying, []);
      map.get(p.underlying)!.push(p);
    }
    for (const arr of map.values()) {
      arr.sort((a, b) => a.phase_no - b.phase_no || String(a.entry_time).localeCompare(String(b.entry_time)));
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [filtered]);

  const allBySymbol = useMemo(() => {
    const map = new Map<string, FrPhase[]>();
    for (const p of allPhases) {
      if (!map.has(p.underlying)) map.set(p.underlying, []);
      map.get(p.underlying)!.push(p);
    }
    for (const arr of map.values()) {
      arr.sort((a, b) => a.phase_no - b.phase_no || String(a.entry_time).localeCompare(String(b.entry_time)));
    }
    return map;
  }, [allPhases]);

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

      {groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">No phase history for the selected date range.</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
          {groups.map(([symbol, phases]) => {
            const allInstrumentPhases = allBySymbol.get(symbol) ?? phases;
            const latestPhase = phases[phases.length - 1];
            const totalMtm = allInstrumentPhases.reduce((sum, p) => sum + phaseMtm(p, liveOpt(p)), 0);
            const realized = allInstrumentPhases.reduce((sum, p) => sum + (p.realized_pnl ?? 0), 0);
            const active = allInstrumentPhases.filter((p) => p.status === "active").length;
            const targetsHit = allInstrumentPhases.reduce((sum, p) => sum + p.targets_achieved.length, 0);
            const targetsTotal = allInstrumentPhases.reduce((sum, p) => sum + p.targets_total, 0);
            const totalTone = totalMtm >= 0 ? "text-emerald-500" : "text-red-500";

            return (
              <section key={symbol} className="fr-glass fr-dark-surface h-fit rounded-2xl border border-border/70 p-4">
                <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
                  <div className="min-w-0">
                    <h3 className="text-2xl font-bold tracking-tight">{symbol}</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Showing latest of {allInstrumentPhases.length} phase(s)
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
                      previousPhases={allInstrumentPhases.filter((item) => item.phase_no > 0 && item.phase_no < latestPhase.phase_no)}
                      liveOptFor={liveOpt}
                      className="bg-card/60"
                    />
                  )}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
