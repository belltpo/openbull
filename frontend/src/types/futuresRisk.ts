// Types for the Futures-Risk Options module (mirrors backend/routers/futures_risk.py).

export type OptionType = "CE" | "PE";
export type Side = "BUY" | "SELL";
export type TradeStatus = "draft" | "active" | "completed" | "stopped" | "cancelled" | "error";
export type TrailingMode = "entry_after_t1" | "prev_target" | "off";
export type TargetStatus = "pending" | "hit" | "skipped";

export interface FrTradeTarget {
  seq: number;
  points: number;
  exit_pct: number;
  trigger_price: number;
  exit_qty: number;
  status: TargetStatus;
  hit_futures_price: number | null;
  exit_order_id: string | null;
  hit_at: string | null;
}

export interface FrEvent {
  id: number;
  trade_id: number | null;
  ts: string | null;
  kind: string;
  severity: string;
  message: string;
  payload: Record<string, unknown> | null;
}

export interface FrTrade {
  id: number;
  mode: "live" | "sandbox";
  underlying: string;
  option_symbol: string;
  option_exchange: string;
  option_type: OptionType;
  side: Side;
  product: string;
  expiry: string | null;
  strike: number | null;
  lots: number;
  lot_size: number;
  total_qty: number;
  remaining_qty: number;
  entry_option_price: number;
  entry_order_id: string | null;
  futures_symbol: string;
  futures_exchange: string;
  entry_futures_price: number;
  direction: number; // +1 bullish, -1 bearish
  sl_points: number;
  sl_price: number;
  sl_basis: string;
  status: TradeStatus;
  realized_pnl: number;
  created_by: number | null;
  modified_by: number | null;
  params: PlaceTradePayload | null;
  trailing_mode: TrailingMode | null;
  phase_group: string | null;
  phase_no: number;
  closed_at: string | null;
  duration_sec: number | null;
  created_at: string | null;
  updated_at: string | null;
  targets: FrTradeTarget[];
  events?: FrEvent[];
}

export interface FrPhase {
  trade_id: number;
  underlying: string;
  phase_group: string | null;
  phase_no: number;
  status: TradeStatus;
  option_symbol: string;
  side: Side;
  option_type: OptionType;
  lots: number;
  entry_time: string | null;
  exit_time: string | null;
  entry_futures_price: number;
  entry_option_price: number;
  sl_price: number;
  sl_basis: string;
  targets_total: number;
  targets_achieved: number[];
  realized_pnl: number;
  remaining_qty: number;
  duration_sec: number | null;
  exit_kind: "auto" | "manual" | "open";
}

export interface ModifyTradePayload {
  // draft-only
  underlying?: string;
  underlying_exchange?: string;
  expiry?: string;
  option_type?: OptionType;
  side?: Side;
  product?: string;
  lots?: number;
  strike?: number | null;
  offset?: string;
  // editable any time
  sl_points?: number;
  targets?: { points: number; exit_pct: number }[];
  trailing_mode?: TrailingMode;
}

export interface FrTemplateTarget {
  id: number;
  seq: number;
  points: number;
  exit_pct: number;
  enabled: boolean;
}

export interface FrSymbolMap {
  id: number;
  underlying: string;
  underlying_exchange: string;
  futures_symbol: string | null;
  futures_exchange: string;
  lot_size: number;
  auto_resolve: boolean;
  enabled: boolean;
}

export interface FrConfigEntry {
  value: string;
  description: string;
  is_editable: boolean;
}
export type FrConfigMap = Record<string, FrConfigEntry>;

export interface FrExpiry {
  display: string;
  value: string;
}

export interface FrStrikes {
  strikes: number[];
  atm: number | null;
  options_exchange: string;
}

export interface FrFutures {
  symbol: string;
  exchange: string;
  lot_size: number;
}

export interface PlaceTradePayload {
  underlying: string;
  underlying_exchange?: string;
  expiry: string;
  option_type: OptionType;
  side: Side;
  product?: string;
  lots: number;
  strike?: number | null;
  offset?: string;
  sl_points?: number | null;
  targets?: { points: number; exit_pct: number }[] | null;
}
