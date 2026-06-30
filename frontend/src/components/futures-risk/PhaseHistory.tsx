/**
 * Phase history — sequential positions grouped by (underlying, session).
 * Each phase shows entry/exit, achieved targets, P&L, duration and exit kind.
 */
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Bot, Hand, Layers } from "lucide-react";

import { cn } from "@/lib/utils";
import { listPhases } from "@/api/futuresRisk";
import type { FrPhase } from "@/types/futuresRisk";
import { durationFmt, fmt, timeFmt } from "./frFormat";

function PhasePill({ p }: { p: FrPhase }) {
  const pnlTone = p.realized_pnl >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400";
  return (
    <div className="fr-glass flex min-w-[180px] flex-col gap-1 rounded-xl p-2.5">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1 text-xs font-semibold text-primary">
          <Layers className="h-3 w-3" /> Phase {p.phase_no}
        </span>
        <span
          className={cn(
            "rounded px-1.5 py-0.5 text-[9px] font-medium",
            p.status === "active" ? "bg-emerald-500/15 text-emerald-600" :
            p.status === "stopped" ? "bg-red-500/15 text-red-600" :
            "bg-sky-500/15 text-sky-600",
          )}
        >
          {p.status}
        </span>
      </div>
      <p className="truncate font-mono text-[10px] text-muted-foreground">{p.option_symbol}</p>
      <div className="flex items-center justify-between text-[11px] tabular-nums">
        <span className="text-muted-foreground">P&L</span>
        <span className={cn("font-semibold", pnlTone)}>₹{fmt(p.realized_pnl)}</span>
      </div>
      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
        <span>
          T{p.targets_achieved.length}/{p.targets_total} · {durationFmt(p.duration_sec)}
        </span>
        <span className="flex items-center gap-0.5">
          {p.exit_kind === "auto" ? <Bot className="h-3 w-3" /> : p.exit_kind === "manual" ? <Hand className="h-3 w-3" /> : null}
          {p.exit_kind !== "open" && p.exit_kind}
        </span>
      </div>
      <div className="text-[9px] text-muted-foreground">
        {timeFmt(p.entry_time)} → {p.exit_time ? timeFmt(p.exit_time) : "open"}
      </div>
    </div>
  );
}

export function PhaseHistory({ underlying, dataOverride }: { underlying?: string; dataOverride?: FrPhase[] }) {
  const { data } = useQuery({
    queryKey: ["fr-phases", underlying ?? "all"],
    queryFn: () => listPhases(underlying),
    refetchInterval: 8000,
    enabled: !dataOverride,
  });

  const groups = useMemo(() => {
    const map = new Map<string, FrPhase[]>();
    for (const p of dataOverride ?? data ?? []) {
      const key = p.phase_group ?? `${p.underlying}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(p);
    }
    for (const arr of map.values()) arr.sort((a, b) => a.phase_no - b.phase_no);
    return Array.from(map.entries());
  }, [data, dataOverride]);

  if (groups.length === 0) {
    return <p className="text-sm text-muted-foreground">No phase history yet — placed positions appear here as Phase 1, 2, 3…</p>;
  }

  return (
    <div className="space-y-4">
      {groups.map(([key, phases]) => {
        const total = phases.reduce((a, p) => a + (p.realized_pnl ?? 0), 0);
        const [, und, session] = key.split(":");
        return (
          <div key={key} className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">
                {und ?? phases[0].underlying} <span className="text-xs font-normal text-muted-foreground">· {session ?? ""}</span>
              </h3>
              <span className={cn("text-xs font-semibold tabular-nums", total >= 0 ? "text-emerald-600" : "text-red-600")}>
                Session P&L ₹{fmt(total)}
              </span>
            </div>
            <div className="flex items-stretch gap-2 overflow-x-auto pb-1">
              {phases.map((p, i) => (
                <div key={p.trade_id} className="flex items-center gap-2">
                  <PhasePill p={p} />
                  {i < phases.length - 1 && <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />}
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
