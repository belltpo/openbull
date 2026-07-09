/**
 * Shared formatting + derived-state helpers for the Futures-Risk dashboard.
 */
import type { FrTrade, TradeStatus } from "@/types/futuresRisk";

export function fmt(n: number | null | undefined, d = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Number(n).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
}

export function signed(n: number | null | undefined, d = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return `${n >= 0 ? "+" : ""}${fmt(n, d)}`;
}

/** Live option-leg P&L for the remaining quantity, given the current premium. */
export function livePnl(trade: FrTrade, liveOpt: number | undefined): number | null {
  if (trade.open_pnl !== null && trade.open_pnl !== undefined) return Number(trade.open_pnl);
  if (liveOpt === undefined || !trade.entry_option_price) return null;
  const dir = trade.side === "BUY" ? 1 : -1;
  return (liveOpt - trade.entry_option_price) * trade.remaining_qty * dir;
}

/** Total P&L = realized (booked exits) + live unrealized (open remainder). */
export function totalPnl(trade: FrTrade, liveOpt: number | undefined): number {
  if (trade.total_pnl !== null && trade.total_pnl !== undefined) return Number(trade.total_pnl);
  const open = livePnl(trade, liveOpt) ?? 0;
  return (trade.realized_pnl ?? 0) + open;
}

export interface StatusMeta {
  label: string;
  /** tailwind text + bg tint classes for the status pill */
  pill: string;
  dot: string;
  live: boolean;
}

export function statusMeta(status: TradeStatus): StatusMeta {
  switch (status) {
    case "draft":
      return { label: "Draft", pill: "bg-amber-400/15 text-amber-600 dark:text-amber-300 border-amber-400/30", dot: "bg-amber-400", live: false };
    case "active":
      return { label: "Active", pill: "bg-emerald-400/15 text-emerald-600 dark:text-emerald-300 border-emerald-400/30", dot: "bg-emerald-400", live: true };
    case "completed":
      return { label: "Completed", pill: "bg-sky-400/15 text-sky-600 dark:text-sky-300 border-sky-400/30", dot: "bg-sky-400", live: false };
    case "stopped":
      return { label: "Stopped", pill: "bg-red-400/15 text-red-600 dark:text-red-300 border-red-400/30", dot: "bg-red-400", live: false };
    case "error":
      return { label: "Failed", pill: "bg-red-500/15 text-red-600 dark:text-red-300 border-red-500/30", dot: "bg-red-500", live: false };
    case "cancelled":
      return { label: "Cancelled", pill: "bg-zinc-400/15 text-zinc-500 dark:text-zinc-300 border-zinc-400/30", dot: "bg-zinc-400", live: false };
    default:
      return { label: status, pill: "bg-zinc-400/15 text-zinc-500 border-zinc-400/30", dot: "bg-zinc-400", live: false };
  }
}

export function durationFmt(sec: number | null | undefined): string {
  if (sec === null || sec === undefined || sec < 0) return "—";
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export function timeFmt(iso: string | null | undefined): string {
  if (!iso) return "—";
  return iso.slice(11, 19);
}
