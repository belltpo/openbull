/**
 * Symbol-grouped phase history for Futures-Risk positions.
 */
import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays, Clock, Layers, Shield, Target, TrendingUp } from "lucide-react";

import { cn } from "@/lib/utils";
import { listPhases } from "@/api/futuresRisk";
import { useMarketData } from "@/hooks/useMarketData";
import type { FrPhase } from "@/types/futuresRisk";
import { durationFmt, fmt, timeFmt } from "./frFormat";

type DateFilter = "today" | "week" | "month" | "custom";

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
}: {
  label: string;
  value: string;
  sub?: string;
  icon?: ReactNode;
  valueClassName?: string;
}) {
  return (
    <div className="rounded-lg border border-border/60 bg-background/40 p-2">
      <div className="flex items-center gap-1 text-[10px] uppercase text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className={cn("mt-1 font-semibold tabular-nums", valueClassName)}>{value}</div>
      {sub ? <div className="mt-0.5 truncate text-[10px] text-muted-foreground">{sub}</div> : null}
    </div>
  );
}

function PhaseCard({ phase, liveOpt }: { phase: FrPhase; liveOpt: number | undefined }) {
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
    <div className="fr-glass rounded-xl border border-border/70 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1 text-sm font-semibold">
              <Layers className="h-3.5 w-3.5" /> Phase {phase.phase_no}
            </span>
            <span className={cn("rounded-md border px-1.5 py-0.5 text-[10px] font-semibold capitalize", statusTone)}>
              {phase.status}
            </span>
          </div>
          <p className="mt-1 truncate font-mono text-[11px] text-muted-foreground">{phase.option_symbol}</p>
        </div>
        <div className="text-right">
          <p className="text-[10px] uppercase text-muted-foreground">Phase MTM</p>
          <p className={cn("text-sm font-bold tabular-nums", pnlTone)}>Rs. {fmt(mtm)}</p>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 text-xs lg:grid-cols-5">
        <Metric label="Phase MTM" value={`Rs. ${fmt(mtm)}`} sub={phase.status === "active" ? "live + booked" : "booked"} valueClassName={pnlTone} />
        <Metric label="Entry" value={fmt(phase.entry_futures_price)} sub={`Option Rs. ${fmt(phase.entry_option_price)}`} />
        <Metric label="Stoploss" value={fmt(phase.sl_price)} sub={phase.sl_basis} icon={<Shield className="h-3 w-3" />} />
        <Metric label="Targets" value={`${completedTargets}/${phase.targets_total}`} sub={`${phase.remaining_qty}/${phase.total_qty} qty`} icon={<Target className="h-3 w-3" />} />
        <Metric label="Duration" value={durationFmt(phase.duration_sec)} sub={`${timeFmt(phase.entry_time)} -> ${phase.exit_time ? timeFmt(phase.exit_time) : "open"}`} icon={<Clock className="h-3 w-3" />} />
      </div>

      {phase.targets.length > 0 && (
        <div className="mt-3 grid grid-cols-2 gap-1.5 sm:grid-cols-4">
          {phase.targets.map((t) => (
            <div
              key={t.seq}
              className={cn(
                "rounded-md border px-2 py-1.5 text-[11px]",
                t.status === "hit"
                  ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-300"
                  : "border-border/60 bg-background/40 text-muted-foreground",
              )}
            >
              <div className="flex justify-between gap-2">
                <span>T{t.seq}</span>
                <span>{t.status}</span>
              </div>
              <div className="mt-0.5 tabular-nums">{fmt(t.trigger_price, 0)}</div>
              <div className="mt-0.5 text-[10px] opacity-80">{fmt(t.points, 0)} pts / {fmt(t.exit_pct, 0)}%</div>
            </div>
          ))}
        </div>
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

  const liveOpt = (p: FrPhase): number | undefined => tickMap.get(`${p.option_exchange}:${p.option_symbol}`)?.data.ltp;

  return (
    <div className="space-y-4">
      <div className="fr-glass flex flex-col gap-3 rounded-xl border border-border/70 p-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-1.5">
          {(["today", "week", "month", "custom"] as DateFilter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "rounded-full px-3 py-1 text-xs font-semibold capitalize transition-colors",
                filter === f ? "bg-primary text-primary-foreground" : "bg-foreground/[0.05] text-muted-foreground hover:text-foreground",
              )}
            >
              {f === "week" ? "Week" : f === "month" ? "Month" : f}
            </button>
          ))}
        </div>
        {filter === "custom" && (
          <div className="flex flex-wrap items-center gap-2">
            <CalendarDays className="h-4 w-4 text-muted-foreground" />
            <input type="date" value={customFrom} onChange={(e) => setCustomFrom(e.target.value)} className="h-8 rounded-md border border-input bg-background px-2 text-xs dark:[color-scheme:dark]" />
            <span className="text-xs text-muted-foreground">to</span>
            <input type="date" value={customTo} onChange={(e) => setCustomTo(e.target.value)} className="h-8 rounded-md border border-input bg-background px-2 text-xs dark:[color-scheme:dark]" />
          </div>
        )}
      </div>

      {groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">No phase history for the selected date range.</p>
      ) : (
        groups.map(([symbol, phases]) => {
          const totalMtm = phases.reduce((sum, p) => sum + phaseMtm(p, liveOpt(p)), 0);
          const realized = phases.reduce((sum, p) => sum + (p.realized_pnl ?? 0), 0);
          const active = phases.filter((p) => p.status === "active").length;
          const targetsHit = phases.reduce((sum, p) => sum + p.targets_achieved.length, 0);
          const targetsTotal = phases.reduce((sum, p) => sum + p.targets_total, 0);
          const totalTone = totalMtm >= 0 ? "text-emerald-500" : "text-red-500";

          return (
            <section key={symbol} className="space-y-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <h3 className="text-lg font-bold tracking-tight">{symbol}</h3>
                  <p className="text-xs text-muted-foreground">{phases.length} phase(s) in selected range</p>
                </div>
                <div className="grid grid-cols-2 gap-2 text-right text-xs sm:grid-cols-4">
                  <Metric label="Overall Instrument MTM" value={`Rs. ${fmt(totalMtm)}`} icon={<TrendingUp className="h-3 w-3" />} valueClassName={totalTone} />
                  <Metric label="Booked P&L" value={`Rs. ${fmt(realized)}`} />
                  <Metric label="Targets" value={`${targetsHit}/${targetsTotal}`} />
                  <Metric label="Active Phases" value={String(active)} />
                </div>
              </div>
              <div className="grid grid-cols-1 gap-3 2xl:grid-cols-2">
                {phases.map((p) => (
                  <PhaseCard key={p.trade_id} phase={p} liveOpt={liveOpt(p)} />
                ))}
              </div>
            </section>
          );
        })
      )}
    </div>
  );
}
