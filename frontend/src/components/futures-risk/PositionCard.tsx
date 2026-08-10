/**
 * Glassmorphism position card — the heart of the Futures-Risk dashboard.
 * Shows real-time futures-vs-option comparison, live P&L, a target progress
 * track, the stop-loss, a lifecycle timeline, and lifecycle actions.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Activity,
  ChevronDown,
  Layers,
  Pencil,
  Play,
  RefreshCw,
  ShieldAlert,
  Target as TargetIcon,
  Trash2,
  TrendingDown,
  TrendingUp,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { getTrade, resumeExitProtection } from "@/api/futuresRisk";
import type { FrTrade } from "@/types/futuresRisk";
import { PositionTimeline } from "./PositionTimeline";
import { durationFmt, fmt, livePnl, signed, statusMeta, timeFmt, totalPnl } from "./frFormat";

interface Props {
  trade: FrTrade;
  liveFut: number | undefined;
  liveOpt: number | undefined;
  previousTrades?: FrTrade[];
  liveOptFor?: (trade: FrTrade) => number | undefined;
  onModify: (t: FrTrade) => void;
  onExit: (t: FrTrade) => void;
  onEmergency: (t: FrTrade) => void;
  onPlaceDraft: (id: number) => void;
  onDelete: (id: number) => void;
  busy?: boolean;
  enableRemoteDetail?: boolean;
}

function localDateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
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

function Metric({ label, value, tone, sub }: { label: string; value: React.ReactNode; tone?: "good" | "bad"; sub?: React.ReactNode }) {
  return (
    <div className="fr-dark-surface min-w-0 rounded-lg border border-border/60 bg-background/45 px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p
        className={cn(
          "truncate text-sm font-semibold tabular-nums",
          tone === "good" && "text-emerald-600 dark:text-emerald-400",
          tone === "bad" && "text-red-600 dark:text-red-400",
        )}
      >
        {value}
      </p>
      {sub && <p className="truncate text-[10px] tabular-nums text-muted-foreground">{sub}</p>}
    </div>
  );
}

function targetQtyLabel(trade: FrTrade, hitCount: number): string {
  if (trade.status === "active" || trade.status === "draft") {
    return `Remaining ${trade.remaining_qty}/${trade.total_qty} qty`;
  }
  const exitedQty = Math.max(0, trade.total_qty - trade.remaining_qty);
  if (trade.status === "stopped") return `Exited ${exitedQty}/${trade.total_qty} via SL`;
  if (trade.status === "completed" && trade.targets.length > 0 && hitCount >= trade.targets.length) {
    return `Exited ${exitedQty}/${trade.total_qty} via targets`;
  }
  return `Exited ${exitedQty}/${trade.total_qty} qty`;
}

function PreviousPhaseCard({ trade, liveOpt }: { trade: FrTrade; liveOpt: number | undefined }) {
  const sm = statusMeta(trade.status);
  const pnl = trade.status === "active" ? totalPnl(trade, liveOpt) : trade.realized_pnl;
  const hitCount = trade.targets.filter((t) => t.status === "hit").length;

  return (
    <div className="fr-dark-surface min-w-0 rounded-xl border border-border/60 bg-background/45 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex items-center gap-1 text-sm font-semibold">
              <Layers className="h-3.5 w-3.5" /> Phase {trade.phase_no}
            </span>
            <span className={cn("rounded-md border px-1.5 py-0.5 text-xs font-semibold", sm.pill)}>{sm.label}</span>
          </div>
          <p className="mt-1 truncate font-mono text-xs text-muted-foreground">{trade.option_symbol}</p>
        </div>
        <p
          className={cn(
            "text-sm font-bold tabular-nums",
            pnl >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400",
          )}
        >
          Rs. {fmt(pnl)}
        </p>
      </div>

      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <Metric label="Entry" value={fmt(trade.entry_futures_price)} sub={`Option Rs. ${fmt(trade.entry_option_price)}`} />
        <Metric label="Stop-Loss" value={fmt(trade.sl_price)} sub={trade.sl_basis} />
        <Metric label="Targets" value={`${hitCount}/${trade.targets.length}`} sub={targetQtyLabel(trade, hitCount)} />
        <Metric label="Duration" value={durationFmt(trade.duration_sec)} sub={`${timeFmt(trade.created_at)} -> ${trade.closed_at ? timeFmt(trade.closed_at) : "open"}`} />
      </div>
    </div>
  );
}

function groupTradesByDate(trades: FrTrade[]) {
  const map = new Map<string, FrTrade[]>();
  for (const trade of trades) {
    const key = isoDateKey(trade.created_at);
    if (!key) continue;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(trade);
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([dateKey, items]) => ({
      dateKey,
      trades: [...items].sort((a, b) => a.phase_no - b.phase_no || String(a.created_at).localeCompare(String(b.created_at))),
    }));
}

function PreviousTradeDateGroup({
  dateKey,
  trades,
  liveOptFor,
}: {
  dateKey: string;
  trades: FrTrade[];
  liveOptFor?: (trade: FrTrade) => number | undefined;
}) {
  const totalMtm = trades.reduce(
    (sum, item) => sum + (item.status === "active" ? totalPnl(item, liveOptFor?.(item)) : item.realized_pnl),
    0,
  );
  const bookedPnl = trades.reduce((sum, item) => sum + (item.realized_pnl ?? 0), 0);
  const targetsHit = trades.reduce((sum, item) => sum + item.targets.filter((target) => target.status === "hit").length, 0);
  const targetsTotal = trades.reduce((sum, item) => sum + item.targets.length, 0);
  const activeCount = trades.filter((item) => item.status === "active").length;
  const totalTone = totalMtm >= 0 ? "good" : "bad";

  return (
    <section className="fr-dark-surface rounded-xl border border-border/70 bg-background/35 p-3">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="text-base font-semibold">{displayDateLabel(dateKey)}</h4>
          <p className="text-xs text-muted-foreground">{trades.length} phase(s) for this instrument</p>
        </div>
        <p
          className={cn(
            "text-base font-bold tabular-nums",
            totalMtm >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400",
          )}
        >
          Rs. {fmt(totalMtm)}
        </p>
      </div>

      <div className="mb-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        <Metric label="Date MTM" value={`Rs. ${fmt(totalMtm)}`} tone={totalTone} />
        <Metric label="Booked P&L" value={`Rs. ${fmt(bookedPnl)}`} tone={bookedPnl >= 0 ? "good" : "bad"} />
        <Metric label="Targets" value={`${targetsHit}/${targetsTotal}`} />
        <Metric label="Active" value={String(activeCount)} />
      </div>

      <details className="group">
        <summary className="fr-dark-surface fr-dark-surface-hover flex cursor-pointer list-none items-center justify-between rounded-lg border border-border/70 bg-background/35 px-3 py-2 text-sm font-semibold text-muted-foreground transition-colors hover:bg-background/55 hover:text-foreground">
          <span>View phases for this date ({trades.length})</span>
          <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
        </summary>
        <div className="mt-3 grid justify-center gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),360px))]">
          {trades.map((item) => (
            <PreviousPhaseCard key={item.id} trade={item} liveOpt={liveOptFor?.(item)} />
          ))}
        </div>
      </details>
    </section>
  );
}

function TargetTrack({ trade, liveFut }: { trade: FrTrade; liveFut: number | undefined }) {
  const entry = trade.entry_futures_price;
  const last = trade.targets[trade.targets.length - 1]?.trigger_price ?? entry;
  const range = last - entry;
  const cur = (liveFut ?? entry) - entry;
  const pct = range !== 0 ? Math.max(0, Math.min(1, cur / range)) * 100 : 0;
  const hitCount = trade.targets.filter((t) => t.status === "hit").length;

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <TargetIcon className="h-3 w-3" /> {hitCount}/{trade.targets.length} targets
        </span>
        <span className="tabular-nums">{pct.toFixed(0)}%</span>
      </div>
      <div className="relative h-2 overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "relative h-full rounded-full bg-gradient-to-r from-emerald-500/70 to-emerald-400",
            trade.status === "active" && "fr-sheen",
          )}
          style={{ width: `${pct}%` }}
        />
        {/* target tick markers */}
        {trade.targets.map((t) => {
          const tp = range !== 0 ? Math.max(0, Math.min(1, (t.trigger_price - entry) / range)) * 100 : 0;
          return (
            <span
              key={t.seq}
              className={cn(
                "absolute top-1/2 h-2.5 w-0.5 -translate-y-1/2 rounded-full",
                t.status === "hit" ? "bg-emerald-700" : "bg-foreground/30",
              )}
              style={{ left: `${tp}%` }}
              title={`T${t.seq} @ ${t.trigger_price}`}
            />
          );
        })}
      </div>
    </div>
  );
}

export function PositionCard({
  trade,
  liveFut,
  liveOpt,
  previousTrades = [],
  liveOptFor,
  onModify,
  onExit,
  onEmergency,
  onPlaceDraft,
  onDelete,
  busy,
  enableRemoteDetail = true,
}: Props) {
  const [showLog, setShowLog] = useState(false);
  const [showPreviousDetail, setShowPreviousDetail] = useState(false);
  const queryClient = useQueryClient();
  const detail = useQuery({
    queryKey: ["fr-trade-detail", trade.mode, trade.id],
    queryFn: () => getTrade(trade.id, trade.mode),
    enabled: showLog && enableRemoteDetail,
    refetchInterval: showLog && trade.status === "active" ? 4000 : false,
  });

  const sm = statusMeta(trade.status);
  const isDraft = trade.status === "draft";
  const isActive = trade.status === "active";
  const isClosed = ["completed", "stopped", "cancelled", "error"].includes(trade.status);
  const exitBlocked = isActive && trade.exit_state === "blocked";
  const exitSubmitting = isActive && trade.exit_state === "submitting";
  const exitRetrying = isActive && trade.exit_state === "retry_wait";
  const exitRetryExhausted = isActive && trade.exit_state === "retry_exhausted";
  const recovery = useMutation({
    mutationFn: () => resumeExitProtection(trade.id),
    onSuccess: (updated) => {
      toast.success(updated.status === "active" ? "Broker verified; exit protection resumed" : "Broker position reconciled");
      queryClient.invalidateQueries({ queryKey: ["fr-trades"] });
      queryClient.invalidateQueries({ queryKey: ["fr-trade-detail", trade.mode, trade.id] });
    },
    onError: (error: unknown) => {
      // @ts-expect-error axios response shape
      toast.error(String(error?.response?.data?.detail ?? "Broker reconciliation failed"));
    },
  });
  const previousByDate = useMemo(() => groupTradesByDate(previousTrades), [previousTrades]);

  const futDelta = liveFut !== undefined ? liveFut - trade.entry_futures_price : null;
  const optDelta = liveOpt !== undefined ? liveOpt - trade.entry_option_price : null;
  const pnl = isActive ? totalPnl(trade, liveOpt) : trade.realized_pnl;
  const openPnl = isActive ? livePnl(trade, liveOpt) : null;
  const buy = trade.side === "BUY";

  return (
    <div className="fr-edge-glow fr-glass fr-dark-position-card relative overflow-hidden rounded-2xl p-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-base font-bold tracking-tight">{trade.underlying}</span>
            <span
              className={cn(
                "rounded-md px-1.5 py-0.5 text-[10px] font-semibold",
                buy ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-300" : "bg-red-500/15 text-red-600 dark:text-red-300",
              )}
            >
              {trade.side} {trade.option_type}
            </span>
            {trade.phase_no > 0 && (
              <span className="flex items-center gap-0.5 rounded-md bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
                <Layers className="h-3 w-3" /> Phase {trade.phase_no}
              </span>
            )}
            {trade.mode === "sandbox" && (
              <span className="rounded-md bg-foreground/10 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">Sandbox</span>
            )}
          </div>
          <p className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground">{trade.option_symbol}</p>
        </div>
        <span className={cn("flex shrink-0 items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium", sm.pill)}>
          <span className={cn("h-1.5 w-1.5 rounded-full", sm.dot, sm.live && "fr-dot-live")} />
          {sm.label}
        </span>
      </div>

      {/* Futures vs Option live comparison */}
      <div className="mt-3 grid grid-cols-2 gap-2">
        <div className="fr-dark-surface min-w-0 rounded-lg border border-border/60 bg-background/45 px-2.5 py-2">
          <p className="flex items-center gap-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            {buy ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />} Futures
          </p>
          <p className="mt-1 truncate text-sm font-semibold tabular-nums">{fmt(liveFut)}</p>
          <p className="truncate text-[10px] tabular-nums text-muted-foreground">
            {futDelta !== null ? <span className={futDelta >= 0 ? "text-emerald-600" : "text-red-600"}>{signed(futDelta)} vs entry</span> : `entry ${fmt(trade.entry_futures_price)}`}
          </p>
        </div>
        <div className="fr-dark-surface min-w-0 rounded-lg border border-border/60 bg-background/45 px-2.5 py-2">
          <p className="flex items-center gap-1 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
            <Activity className="h-3 w-3" /> Option premium
          </p>
          <p className="mt-1 truncate text-sm font-semibold tabular-nums">{fmt(liveOpt)}</p>
          <p className="truncate text-[10px] tabular-nums text-muted-foreground">
            {optDelta !== null ? <span className={optDelta >= 0 ? "text-emerald-600" : "text-red-600"}>{signed(optDelta)} vs entry</span> : `entry ${fmt(trade.entry_option_price)}`}
          </p>
        </div>
      </div>

      {/* P&L + SL + qty */}
      <div className="mt-2 grid grid-cols-3 gap-2">
        <Metric
          label={isActive ? "Total P&L" : "Realized P&L"}
          value={`₹${fmt(pnl)}`}
          tone={pnl >= 0 ? "good" : "bad"}
          sub={openPnl !== null ? `open ${signed(openPnl)}` : undefined}
        />
        <Metric label="Stop-Loss" value={fmt(trade.sl_price)} sub={trade.sl_basis} />
        <Metric label="Remaining" value={`${trade.remaining_qty}/${trade.total_qty}`} sub={`${trade.lots} lot${trade.lots > 1 ? "s" : ""}`} />
      </div>

      {/* Target progress */}
      <div className="mt-3">
        <TargetTrack trade={trade} liveFut={liveFut} />
      </div>

      {/* Timeline */}
      <div className="mt-3 border-t border-border/60 pt-3">
        <PositionTimeline trade={trade} liveOpt={liveOpt} />
      </div>

      {exitBlocked && (
        <div className="mt-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-2.5 text-xs text-amber-700 dark:text-amber-300">
          <div className="flex items-start gap-2">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">Automatic exits paused after one failed attempt</p>
              <p className="mt-0.5 break-words opacity-90">{trade.exit_block_reason ?? "Broker result needs verification."}</p>
              <Button
                size="sm"
                variant="outline"
                className="mt-2 h-7 border-amber-500/40 bg-background/60"
                disabled={recovery.isPending}
                onClick={() => recovery.mutate()}
              >
                <RefreshCw className={cn("mr-1 h-3.5 w-3.5", recovery.isPending && "animate-spin")} />
                Verify broker & resume
              </Button>
            </div>
          </div>
        </div>
      )}

      {(exitRetrying || exitRetryExhausted) && (
        <div className="mt-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-2.5 text-xs text-amber-700 dark:text-amber-300">
          <div className="flex items-start gap-2">
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">
                {exitRetryExhausted ? "Automatic exit retry limit reached" : "Broker rejected the exit; safe retry pending"}
              </p>
              <p className="mt-0.5 break-words opacity-90">
                {trade.exit_block_reason ?? "OpenBull will verify the broker position before another order is submitted."}
              </p>
              {exitRetryExhausted && (
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-2 h-7 border-amber-500/40 bg-background/60"
                  disabled={recovery.isPending}
                  onClick={() => recovery.mutate()}
                >
                  <RefreshCw className={cn("mr-1 h-3.5 w-3.5", recovery.isPending && "animate-spin")} />
                  Verify broker &amp; resume
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {isDraft && (
          <>
            <Button size="sm" onClick={() => onPlaceDraft(trade.id)} disabled={busy} className="bg-emerald-600 text-white hover:bg-emerald-700">
              <Play className="mr-1 h-3.5 w-3.5" /> Place
            </Button>
            <Button size="sm" variant="outline" onClick={() => onModify(trade)}>
              <Pencil className="mr-1 h-3.5 w-3.5" /> Edit
            </Button>
            <Button size="sm" variant="ghost" onClick={() => onDelete(trade.id)} className="text-red-600 hover:text-red-700">
              <Trash2 className="mr-1 h-3.5 w-3.5" /> Delete
            </Button>
          </>
        )}
        {isActive && (
          <>
            <Button size="sm" variant="outline" onClick={() => onModify(trade)} disabled={exitSubmitting || exitBlocked}>
              <Pencil className="mr-1 h-3.5 w-3.5" /> Modify
            </Button>
            <Button size="sm" onClick={() => onExit(trade)} disabled={exitSubmitting || exitBlocked}>
              <TargetIcon className="mr-1 h-3.5 w-3.5" /> Close / Partial
            </Button>
            <Button size="sm" variant="ghost" onClick={() => onEmergency(trade)} disabled={exitSubmitting || exitBlocked} className="text-red-600 hover:bg-red-500/10 hover:text-red-700">
              <Zap className="mr-1 h-3.5 w-3.5" /> Emergency
            </Button>
          </>
        )}
        {isClosed && (
          <Button size="sm" variant="ghost" onClick={() => onDelete(trade.id)} className="text-muted-foreground">
            <Trash2 className="mr-1 h-3.5 w-3.5" /> Remove
          </Button>
        )}
        <button
          className="ml-auto flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
          onClick={() => setShowLog((s) => !s)}
        >
          History <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", showLog && "rotate-180")} />
        </button>
      </div>

      {/* Audit log */}
      {showLog && (
        <div className="mt-2 max-h-48 space-y-1 overflow-auto rounded-xl bg-foreground/[0.03] p-2.5 text-[11px]">
          {isClosed && (
            <p className="mb-1 text-muted-foreground">
              Duration {durationFmt(trade.duration_sec)} · closed {timeFmt(trade.closed_at)}
            </p>
          )}
          {(detail.data?.events ?? trade.events ?? []).map((e) => (
            <div key={e.id} className="flex gap-2">
              <span className="shrink-0 tabular-nums text-muted-foreground">{timeFmt(e.ts)}</span>
              <span
                className={cn(
                  e.severity === "error" && "text-red-600",
                  e.severity === "warning" && "text-amber-600",
                  e.kind === "target_hit" && "text-emerald-600",
                  e.kind === "phase_change" && "text-primary",
                )}
              >
                {e.message}
              </span>
            </div>
          ))}
          {detail.isLoading && <p className="text-muted-foreground">Loading…</p>}
          {!detail.isLoading && (detail.data?.events ?? trade.events ?? []).length === 0 && (
            <p className="text-muted-foreground">No events yet.</p>
          )}
        </div>
      )}

      {previousTrades.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setShowPreviousDetail(true)}
            className="fr-dark-surface fr-dark-surface-hover mt-3 flex w-full items-center justify-between gap-3 rounded-xl border border-border/70 bg-background/30 px-3 py-2.5 text-left text-sm font-semibold text-muted-foreground transition-colors hover:bg-background/55 hover:text-foreground"
          >
            <span>Earlier phases for this instrument ({previousTrades.length})</span>
            <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", showPreviousDetail && "rotate-180")} />
          </button>

          <Dialog open={showPreviousDetail} onOpenChange={setShowPreviousDetail}>
            <DialogContent className="fr-dark-dialog max-h-[90vh] w-[calc(100vw-1rem)] overflow-hidden p-0 sm:max-w-[min(980px,calc(100vw-2rem))]">
              <div className="scrollbar-hidden max-h-[90vh] space-y-4 overflow-y-auto overscroll-contain p-4 pr-5 sm:p-5 sm:pr-6">
                <DialogHeader>
                  <DialogTitle className="text-xl font-semibold">
                    {trade.underlying} phase details
                  </DialogTitle>
                  <DialogDescription>
                    Earlier phases grouped by trading date. Each date shows instrument MTM, booked P&L, targets, and phase details.
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-3">
                  {previousByDate.map((group) => (
                    <PreviousTradeDateGroup
                      key={group.dateKey}
                      dateKey={group.dateKey}
                      trades={group.trades}
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
