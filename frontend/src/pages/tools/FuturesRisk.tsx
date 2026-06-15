import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, Settings, X } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";
import { useMarketData } from "@/hooks/useMarketData";
import { exitTrade, getTrade, listTrades } from "@/api/futuresRisk";
import type { FrTrade } from "@/types/futuresRisk";
import { FuturesRiskOrderPopup } from "@/components/futures-risk/OrderPopup";

const STATUS_FILTERS = ["active", "all", "completed", "stopped"] as const;
type StatusFilter = (typeof STATUS_FILTERS)[number];

function fmt(n: number | null | undefined, d = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
}

function StatCard({ label, value, tone }: { label: string; value: string | number; tone?: "good" | "bad" }) {
  return (
    <Card>
      <CardContent className="p-3">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p
          className={cn(
            "mt-1 text-lg font-semibold tabular-nums",
            tone === "good" && "text-emerald-600 dark:text-emerald-400",
            tone === "bad" && "text-red-600 dark:text-red-400",
          )}
        >
          {value}
        </p>
      </CardContent>
    </Card>
  );
}

function pnlFor(trade: FrTrade, liveOpt: number | undefined): number | null {
  if (liveOpt === undefined || !trade.entry_option_price) return null;
  const dir = trade.side === "BUY" ? 1 : -1;
  return (liveOpt - trade.entry_option_price) * trade.remaining_qty * dir;
}

function TradeCard({
  trade,
  liveFut,
  liveOpt,
  onExit,
  exiting,
}: {
  trade: FrTrade;
  liveFut: number | undefined;
  liveOpt: number | undefined;
  onExit: (id: number) => void;
  exiting: boolean;
}) {
  const [showLog, setShowLog] = useState(false);
  const detailQuery = useQuery({
    queryKey: ["fr-trade-detail", trade.id],
    queryFn: () => getTrade(trade.id),
    enabled: showLog,
    refetchInterval: showLog ? 4000 : false,
  });

  const futDelta = liveFut !== undefined ? liveFut - trade.entry_futures_price : null;
  const pnl = pnlFor(trade, liveOpt);
  const isActive = trade.status === "active";
  const statusTone =
    trade.status === "active" ? "default" : trade.status === "stopped" ? "destructive" : "secondary";

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <span>{trade.underlying}</span>
              <Badge
                className={cn(
                  trade.side === "BUY" ? "bg-green-600 text-white" : "bg-red-600 text-white",
                )}
              >
                {trade.side} {trade.option_type}
              </Badge>
              {trade.mode === "sandbox" && <Badge variant="outline">Sandbox</Badge>}
            </CardTitle>
            <p className="mt-0.5 font-mono text-xs text-muted-foreground">{trade.option_symbol}</p>
          </div>
          <Badge variant={statusTone as "default" | "destructive" | "secondary"}>{trade.status}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Futures + option + pnl */}
        <div className="grid grid-cols-3 gap-2 text-xs">
          <div>
            <p className="text-muted-foreground">Entry Futures</p>
            <p className="font-semibold tabular-nums">{fmt(trade.entry_futures_price)}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Live Futures</p>
            <p className="font-semibold tabular-nums">
              {fmt(liveFut)}{" "}
              {futDelta !== null && (
                <span className={cn(futDelta >= 0 ? "text-emerald-600" : "text-red-600")}>
                  ({futDelta >= 0 ? "+" : ""}
                  {fmt(futDelta)})
                </span>
              )}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Live P&amp;L</p>
            <p
              className={cn(
                "font-semibold tabular-nums",
                pnl !== null && pnl >= 0 ? "text-emerald-600" : pnl !== null ? "text-red-600" : "",
              )}
            >
              {pnl === null ? "—" : `₹${fmt(pnl)}`}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2 text-xs">
          <div>
            <p className="text-muted-foreground">Remaining</p>
            <p className="font-semibold tabular-nums">
              {trade.remaining_qty}/{trade.total_qty}
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Stop-Loss</p>
            <p className="font-semibold tabular-nums">
              {fmt(trade.sl_price)} <span className="text-[10px] text-muted-foreground">({trade.sl_basis})</span>
            </p>
          </div>
          <div>
            <p className="text-muted-foreground">Entry Opt</p>
            <p className="font-semibold tabular-nums">{fmt(trade.entry_option_price)}</p>
          </div>
        </div>

        {/* Targets */}
        <div className="flex flex-wrap gap-1.5">
          {trade.targets.map((t) => (
            <span
              key={t.seq}
              className={cn(
                "rounded px-1.5 py-0.5 text-[11px] font-medium tabular-nums",
                t.status === "hit"
                  ? "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300"
                  : "bg-muted text-muted-foreground",
              )}
              title={`Exit ${t.exit_qty} qty at futures ${t.trigger_price}`}
            >
              T{t.seq} {fmt(t.trigger_price, 0)} {t.status === "hit" ? "✓" : ""}
            </span>
          ))}
        </div>

        <div className="flex items-center justify-between">
          <button
            className="text-xs text-muted-foreground underline-offset-2 hover:underline"
            onClick={() => setShowLog((s) => !s)}
          >
            {showLog ? "Hide" : "Auto-exit log"}
          </button>
          {isActive && (
            <Button size="sm" variant="destructive" disabled={exiting} onClick={() => onExit(trade.id)}>
              <X className="mr-1 h-3.5 w-3.5" /> Exit now
            </Button>
          )}
        </div>

        {showLog && (
          <div className="max-h-40 space-y-1 overflow-auto rounded-lg bg-muted/40 p-2 text-[11px]">
            {(detailQuery.data?.events ?? []).map((e) => (
              <div key={e.id} className="flex gap-2">
                <span className="shrink-0 text-muted-foreground">{e.ts?.slice(11, 19)}</span>
                <span
                  className={cn(
                    e.severity === "error" && "text-red-600",
                    e.severity === "warning" && "text-amber-600",
                    e.kind === "target_hit" && "text-emerald-600",
                  )}
                >
                  {e.message}
                </span>
              </div>
            ))}
            {detailQuery.data && (detailQuery.data.events ?? []).length === 0 && (
              <p className="text-muted-foreground">No events yet.</p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function FuturesRisk() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [popupOpen, setPopupOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("active");

  const tradesQuery = useQuery({
    queryKey: ["fr-trades", statusFilter],
    queryFn: () => listTrades(statusFilter),
    refetchInterval: 4000,
  });

  const trades = tradesQuery.data ?? [];

  // Live subscription set: each active trade's futures + option symbol.
  const subscriptionSymbols = useMemo(() => {
    const seen = new Set<string>();
    const out: Array<{ symbol: string; exchange: string }> = [];
    for (const t of trades) {
      if (t.status !== "active") continue;
      for (const pair of [
        { symbol: t.futures_symbol, exchange: t.futures_exchange },
        { symbol: t.option_symbol, exchange: t.option_exchange },
      ]) {
        const k = `${pair.exchange}:${pair.symbol}`;
        if (!seen.has(k)) {
          seen.add(k);
          out.push(pair);
        }
      }
    }
    return out;
  }, [trades]);

  const { data: tickMap } = useMarketData({
    symbols: subscriptionSymbols,
    mode: "LTP",
    enabled: subscriptionSymbols.length > 0,
  });

  const ltpOf = (symbol: string, exchange: string): number | undefined =>
    tickMap.get(`${exchange}:${symbol}`)?.data.ltp;

  const exitMutation = useMutation({
    mutationFn: (id: number) => exitTrade(id),
    onSuccess: () => {
      toast.success("Exit order placed");
      qc.invalidateQueries({ queryKey: ["fr-trades"] });
    },
    onError: (err: unknown) => {
      // @ts-expect-error axios error shape
      toast.error(String(err?.response?.data?.detail ?? "Exit failed"));
    },
  });

  const activeCount = trades.filter((t) => t.status === "active").length;
  const livePnl = useMemo(
    () =>
      trades
        .filter((t) => t.status === "active")
        .reduce((acc, t) => acc + (pnlFor(t, ltpOf(t.option_symbol, t.option_exchange)) ?? 0), 0),
    [trades, tickMap],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Futures-Risk Options</h1>
          <p className="text-sm text-muted-foreground">
            Trade options; targets &amp; stop-loss are managed on the underlying futures price with automatic exits.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {user?.is_admin && (
            <Link to="/tools/futures-risk/admin" className={cn(buttonVariants({ variant: "outline" }))}>
              <Settings className="mr-1 h-4 w-4" /> Admin
            </Link>
          )}
          <Button onClick={() => setPopupOpen(true)}>
            <Plus className="mr-1 h-4 w-4" /> New Order
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Active trades" value={activeCount} />
        <StatCard label="Total trades" value={trades.length} />
        <StatCard
          label="Live P&L (active)"
          value={`₹${fmt(livePnl)}`}
          tone={livePnl >= 0 ? "good" : "bad"}
        />
        <StatCard label="Filter" value={statusFilter} />
      </div>

      <div className="flex flex-wrap gap-1.5">
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium capitalize transition-colors",
              statusFilter === s ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80",
            )}
          >
            {s}
          </button>
        ))}
      </div>

      {trades.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-12 text-center">
            <p className="text-sm text-muted-foreground">
              No {statusFilter === "all" ? "" : statusFilter} trades yet.
            </p>
            <Button onClick={() => setPopupOpen(true)}>
              <Plus className="mr-1 h-4 w-4" /> Place your first order
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {trades.map((t) => (
            <TradeCard
              key={t.id}
              trade={t}
              liveFut={ltpOf(t.futures_symbol, t.futures_exchange)}
              liveOpt={ltpOf(t.option_symbol, t.option_exchange)}
              onExit={(id) => exitMutation.mutate(id)}
              exiting={exitMutation.isPending}
            />
          ))}
        </div>
      )}

      <FuturesRiskOrderPopup
        open={popupOpen}
        onOpenChange={setPopupOpen}
        onPlaced={() => qc.invalidateQueries({ queryKey: ["fr-trades"] })}
      />
    </div>
  );
}
