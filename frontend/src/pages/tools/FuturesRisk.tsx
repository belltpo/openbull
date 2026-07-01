import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Activity, History, LayoutGrid, Plus, Settings, TrendingUp, Wallet, Zap } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import { useMarketData } from "@/hooks/useMarketData";
import { deleteTrade, listTrades, placeDraft } from "@/api/futuresRisk";
import type { FrTrade } from "@/types/futuresRisk";
import { FuturesRiskOrderPopup } from "@/components/futures-risk/OrderPopup";
import { PositionCard } from "@/components/futures-risk/PositionCard";
import { ModifyPositionDialog } from "@/components/futures-risk/ModifyPositionDialog";
import { ExitDialog } from "@/components/futures-risk/ExitDialog";
import { PhaseHistory } from "@/components/futures-risk/PhaseHistory";
import { fmt, livePnl, totalPnl } from "@/components/futures-risk/frFormat";
import { makeFuturesRiskDemoData } from "@/components/futures-risk/demoData";

const STATUS_FILTERS = ["active", "draft", "all", "completed", "stopped"] as const;
type StatusFilter = (typeof STATUS_FILTERS)[number];

function HeroStat({
  icon,
  label,
  value,
  tone,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  tone?: "good" | "bad";
  accent?: string;
}) {
  return (
    <div className="fr-glass fr-edge-glow relative overflow-hidden rounded-2xl p-4">
      <div className="flex items-center justify-between">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <span className={cn("flex h-7 w-7 items-center justify-center rounded-lg bg-foreground/[0.05]", accent)}>{icon}</span>
      </div>
      <p
        className={cn(
          "mt-2 text-2xl font-bold tabular-nums",
          tone === "good" && "text-emerald-600 dark:text-emerald-400",
          tone === "bad" && "text-red-600 dark:text-red-400",
        )}
      >
        {value}
      </p>
    </div>
  );
}

function InstrumentStat({
  label,
  value,
  tone,
  icon,
}: {
  label: string;
  value: string;
  tone?: "good" | "bad";
  icon?: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border/60 bg-card/55 p-3 text-right">
      <div className="flex items-center justify-between gap-2 text-[11px] uppercase text-muted-foreground">
        <span className="flex items-center gap-1">{icon}{label}</span>
      </div>
      <p
        className={cn(
          "mt-1.5 text-sm font-bold tabular-nums",
          tone === "good" && "text-emerald-600 dark:text-emerald-400",
          tone === "bad" && "text-red-600 dark:text-red-400",
        )}
      >
        {value}
      </p>
    </div>
  );
}

export default function FuturesRisk() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const demoEnabled = searchParams.get("demo") === "1";
  const demoData = useMemo(() => makeFuturesRiskDemoData(), []);
  const [popupOpen, setPopupOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("active");
  const [tab, setTab] = useState<"positions" | "phases">("positions");

  const [modifyTarget, setModifyTarget] = useState<FrTrade | null>(null);
  const [exitTarget, setExitTarget] = useState<FrTrade | null>(null);
  const [exitMode, setExitMode] = useState<"full" | "emergency">("full");

  const tradesQuery = useQuery({
    queryKey: ["fr-trades", statusFilter],
    queryFn: () => listTrades(statusFilter),
    refetchInterval: 4000,
    enabled: !demoEnabled,
  });
  const trades = demoEnabled
    ? demoData.trades.filter((trade) => statusFilter === "all" || trade.status === statusFilter)
    : tradesQuery.data ?? [];

  const allTradesQuery = useQuery({
    queryKey: ["fr-trades", "all"],
    queryFn: () => listTrades("all"),
    refetchInterval: 4000,
    enabled: !demoEnabled,
  });
  const allTrades = demoEnabled ? demoData.trades : allTradesQuery.data ?? (statusFilter === "all" ? trades : []);

  // Subscribe to every active trade's futures + option symbol.
  const subscriptionSymbols = useMemo(() => {
    const seen = new Set<string>();
    const out: Array<{ symbol: string; exchange: string }> = [];
    const liveTrades = [...trades, ...allTrades].filter((t, index, arr) => arr.findIndex((item) => item.id === t.id) === index);
    for (const t of liveTrades) {
      if (t.status !== "active" && t.status !== "draft") continue;
      for (const pair of [
        { symbol: t.futures_symbol, exchange: t.futures_exchange },
        { symbol: t.option_symbol, exchange: t.option_exchange },
      ]) {
        const k = `${pair.exchange}:${pair.symbol}`;
        if (pair.symbol && !seen.has(k)) {
          seen.add(k);
          out.push(pair);
        }
      }
    }
    return out;
  }, [trades, allTrades]);

  const { data: tickMap } = useMarketData({
    symbols: subscriptionSymbols,
    mode: "LTP",
    enabled: !demoEnabled && subscriptionSymbols.length > 0,
  });
  const ltpOf = (symbol: string, exchange: string): number | undefined =>
    demoEnabled ? demoData.prices.get(`${exchange}:${symbol}`) : tickMap.get(`${exchange}:${symbol}`)?.data.ltp;

  const placeMutation = useMutation({
    mutationFn: (id: number) => placeDraft(id),
    onSuccess: () => {
      toast.success("Draft placed");
      qc.invalidateQueries({ queryKey: ["fr-trades"] });
    },
    onError: (err: unknown) => {
      // @ts-expect-error axios error shape
      toast.error(String(err?.response?.data?.detail ?? "Place failed"));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteTrade(id),
    onSuccess: () => {
      toast.success("Removed");
      qc.invalidateQueries({ queryKey: ["fr-trades"] });
    },
    onError: (err: unknown) => {
      // @ts-expect-error axios error shape
      toast.error(String(err?.response?.data?.detail ?? "Delete failed"));
    },
  });

  const activeCount = trades.filter((t) => t.status === "active").length;
  const draftCount = trades.filter((t) => t.status === "draft").length;
  const liveUnrealized = useMemo(
    () =>
      trades
        .filter((t) => t.status === "active")
        .reduce((acc, t) => acc + (livePnl(t, ltpOf(t.option_symbol, t.option_exchange)) ?? 0), 0),
    [trades, tickMap],
  );
  const realizedTotal = useMemo(() => trades.reduce((a, t) => a + (t.realized_pnl ?? 0), 0), [trades]);
  const positionGroups = useMemo(() => {
    const map = new Map<string, FrTrade[]>();
    for (const trade of trades) {
      if (!map.has(trade.underlying)) map.set(trade.underlying, []);
      map.get(trade.underlying)!.push(trade);
    }
    for (const group of map.values()) {
      group.sort((a, b) => b.phase_no - a.phase_no || String(b.created_at).localeCompare(String(a.created_at)));
    }
    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  }, [trades]);

  const allByInstrument = useMemo(() => {
    const map = new Map<string, FrTrade[]>();
    for (const trade of allTrades) {
      if (!map.has(trade.underlying)) map.set(trade.underlying, []);
      map.get(trade.underlying)!.push(trade);
    }
    for (const group of map.values()) {
      group.sort((a, b) => a.phase_no - b.phase_no || String(a.created_at).localeCompare(String(b.created_at)));
    }
    return map;
  }, [allTrades]);
  const demoOnly = () => toast.info("Demo data only - no broker action sent");
  const toggleDemo = () => {
    const next = new URLSearchParams(searchParams);
    if (demoEnabled) next.delete("demo");
    else next.set("demo", "1");
    setSearchParams(next);
  };

  return (
    <div className="fr-grid-bg -m-2 space-y-5 rounded-2xl p-2 md:-m-4 md:p-4">
      {/* Header */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="bg-gradient-to-r from-foreground to-foreground/60 bg-clip-text text-2xl font-bold tracking-tight text-transparent">
            Futures-Risk Options
          </h1>
          <p className="text-sm text-muted-foreground">
            Execute in options — targets, stop-loss &amp; trailing all driven by the underlying futures price.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant={demoEnabled ? "default" : "outline"} onClick={toggleDemo}>
            {demoEnabled ? "Demo On" : "Demo Data"}
          </Button>
          {user?.is_admin && (
            <Link to="/tools/futures-risk/admin" className={cn(buttonVariants({ variant: "outline" }))}>
              <Settings className="mr-1 h-4 w-4" /> Admin
            </Link>
          )}
          <Button onClick={() => setPopupOpen(true)} className="shadow-lg shadow-primary/20">
            <Plus className="mr-1 h-4 w-4" /> New Order
          </Button>
        </div>
      </div>

      {/* Hero stats */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <HeroStat
          icon={<TrendingUp className="h-4 w-4" />}
          label="Unrealized P&L"
          value={`₹${fmt(liveUnrealized)}`}
          tone={liveUnrealized >= 0 ? "good" : "bad"}
          accent="text-emerald-500"
        />
        <HeroStat
          icon={<Wallet className="h-4 w-4" />}
          label="Realized P&L"
          value={`₹${fmt(realizedTotal)}`}
          tone={realizedTotal >= 0 ? "good" : "bad"}
          accent="text-sky-500"
        />
        <HeroStat icon={<Activity className="h-4 w-4" />} label="Active" value={String(activeCount)} accent="text-primary" />
        <HeroStat icon={<Zap className="h-4 w-4" />} label="Drafts" value={String(draftCount)} accent="text-amber-500" />
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 rounded-xl bg-foreground/[0.04] p-1 w-fit">
        <button
          onClick={() => setTab("positions")}
          className={cn(
            "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
            tab === "positions" ? "fr-glass-strong text-foreground" : "text-muted-foreground hover:text-foreground",
          )}
        >
          <LayoutGrid className="h-4 w-4" /> Positions
        </button>
        <button
          onClick={() => setTab("phases")}
          className={cn(
            "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
            tab === "phases" ? "fr-glass-strong text-foreground" : "text-muted-foreground hover:text-foreground",
          )}
        >
          <History className="h-4 w-4" /> Phase history
        </button>
      </div>

      {tab === "positions" ? (
        <>
          {/* Filters */}
          <div className="flex flex-wrap gap-1.5">
            {STATUS_FILTERS.map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={cn(
                  "rounded-full px-3 py-1 text-xs font-medium capitalize transition-colors",
                  statusFilter === s ? "bg-primary text-primary-foreground shadow" : "bg-foreground/[0.05] text-muted-foreground hover:bg-foreground/10",
                )}
              >
                {s}
              </button>
            ))}
          </div>

          {trades.length === 0 ? (
            <div className="fr-glass flex flex-col items-center gap-3 rounded-2xl py-16 text-center">
              <p className="text-sm text-muted-foreground">No {statusFilter === "all" ? "" : statusFilter} positions yet.</p>
              <Button onClick={() => setPopupOpen(true)}>
                <Plus className="mr-1 h-4 w-4" /> Place your first order
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-2 min-[1900px]:grid-cols-3">
              {positionGroups.map(([symbol, symbolTrades]) => {
                const instrumentTrades = allByInstrument.get(symbol) ?? symbolTrades;
                const phaseTrades = instrumentTrades.filter((trade) => trade.phase_no > 0);
                const instrumentPnl = phaseTrades.reduce(
                  (sum, trade) =>
                    sum +
                    (trade.status === "active"
                      ? totalPnl(trade, ltpOf(trade.option_symbol, trade.option_exchange))
                      : trade.realized_pnl ?? 0),
                  0,
                );
                const bookedPnl = phaseTrades.reduce((sum, trade) => sum + (trade.realized_pnl ?? 0), 0);
                const targetsHit = phaseTrades.reduce((sum, trade) => sum + trade.targets.filter((target) => target.status === "hit").length, 0);
                const targetsTotal = phaseTrades.reduce((sum, trade) => sum + trade.targets.length, 0);
                const activePhases = phaseTrades.filter((trade) => trade.status === "active").length;
                const pnlTone = instrumentPnl >= 0 ? "good" : "bad";

                return (
                  <section key={symbol} className="fr-glass h-fit rounded-2xl border border-border/70 p-4">
                    <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
                      <div className="min-w-0">
                        <h3 className="text-2xl font-bold tracking-tight">{symbol}</h3>
                        <p className="mt-1 text-sm text-muted-foreground">
                          Showing {symbolTrades.length} of {instrumentTrades.length} position(s)
                        </p>
                      </div>
                    </div>

                    <aside className="mb-3 grid grid-cols-2 gap-2 text-sm">
                      <InstrumentStat
                        icon={<TrendingUp className="h-3 w-3" />}
                        label="Overall Instrument P&L"
                        value={`Rs. ${fmt(instrumentPnl)}`}
                        tone={pnlTone}
                      />
                      <InstrumentStat label="Booked P&L" value={`Rs. ${fmt(bookedPnl)}`} tone={bookedPnl >= 0 ? "good" : "bad"} />
                      <InstrumentStat label="Targets" value={`${targetsHit}/${targetsTotal}`} />
                      <InstrumentStat label="Active Phases" value={String(activePhases)} />
                    </aside>

                    <div className="grid grid-cols-1 gap-3">
                      <div className="grid min-w-0 grid-cols-1 gap-3">
                        {symbolTrades.map((t) => {
                          const previousTrades = phaseTrades.filter((item) => item.phase_no > 0 && item.phase_no < t.phase_no);
                          return (
                            <PositionCard
                              key={t.id}
                              trade={t}
                              liveFut={ltpOf(t.futures_symbol, t.futures_exchange)}
                              liveOpt={ltpOf(t.option_symbol, t.option_exchange)}
                              previousTrades={previousTrades}
                              liveOptFor={(item) => ltpOf(item.option_symbol, item.option_exchange)}
                              onModify={(tr) => (demoEnabled ? demoOnly() : setModifyTarget(tr))}
                              enableRemoteDetail={!demoEnabled}
                              onExit={(tr) => {
                                if (demoEnabled) {
                                  demoOnly();
                                } else {
                                  setExitMode("full");
                                  setExitTarget(tr);
                                }
                              }}
                              onEmergency={(tr) => {
                                if (demoEnabled) {
                                  demoOnly();
                                } else {
                                  setExitMode("emergency");
                                  setExitTarget(tr);
                                }
                              }}
                              onPlaceDraft={(id) => (demoEnabled ? demoOnly() : placeMutation.mutate(id))}
                              onDelete={(id) => (demoEnabled ? demoOnly() : deleteMutation.mutate(id))}
                              busy={placeMutation.isPending || deleteMutation.isPending}
                            />
                          );
                        })}
                      </div>
                    </div>
                  </section>
                );
              })}
            </div>
          )}
        </>
      ) : (
        <PhaseHistory dataOverride={demoEnabled ? demoData.phases : undefined} />
      )}

      {/* Dialogs */}
      <FuturesRiskOrderPopup
        open={popupOpen}
        onOpenChange={setPopupOpen}
        onPlaced={() => qc.invalidateQueries({ queryKey: ["fr-trades"] })}
      />
      <ModifyPositionDialog trade={modifyTarget} open={!!modifyTarget} onOpenChange={(o) => !o && setModifyTarget(null)} />
      <ExitDialog
        trade={exitTarget}
        open={!!exitTarget}
        initialMode={exitMode}
        onOpenChange={(o) => !o && setExitTarget(null)}
      />
    </div>
  );
}
