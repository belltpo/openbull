// Types for the Futures-Risk Options module (mirrors backend/routers/futures_risk.py).

export type OptionType = "CE" | "PE";
export type Side = "BUY" | "SELL";
export type TradeStatus = "draft" | "active" | "completed" | "stopped" | "cancelled" | "error";
export type ExitSafetyState = "idle" | "submitting" | "retry_wait" | "retry_exhausted" | "blocked";
export type TrailingMode = "entry_after_t1" | "prev_target" | "off";
export type TargetStatus = "pending" | "hit" | "skipped";
export type StrikeSelectionMethod = "ATM" | "ITM_OTM" | "MANUAL" | "OFFSET";

export const MONEYNESS_SELECTIONS = [
  "ITM1", "ITM2", "ITM3", "ITM4", "ITM5", "ITM6", "ITM7", "ITM8", "ITM9", "ITM10",
  "ATM",
  "OTM1", "OTM2", "OTM3", "OTM4", "OTM5", "OTM6", "OTM7", "OTM8", "OTM9", "OTM10",
] as const;
export type MoneynessSelection = (typeof MONEYNESS_SELECTIONS)[number];

export interface FrTradeTarget {
  seq: number;
  points: number;
  exit_pct: number;
  trigger_price: number;
  exit_qty: number;
  status: TargetStatus;
  hit_futures_price: number | null;
  exit_order_id: string | null;
  exit_option_price: number | null;
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
  pnl_qty?: number;
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
  exit_state?: ExitSafetyState;
  exit_attempt_reason?: string | null;
  exit_attempted_at?: string | null;
  exit_failure_count?: number;
  exit_block_reason?: string | null;
  last_exit_order_id?: string | null;
  broker_remaining_qty?: number | null;
  broker_reconciled_at?: string | null;
  created_by: number | null;
  modified_by: number | null;
  params: PlaceTradePayload | null;
  trailing_mode: TrailingMode | null;
  phase_group: string | null;
  phase_no: number;
  closed_at: string | null;
  duration_sec: number | null;
  sl_exit_option_price?: number | null;
  created_at: string | null;
  updated_at: string | null;
  targets: FrTradeTarget[];
  events?: FrEvent[];
}

export interface FrPhase {
  trade_id: number;
  mode: "live" | "sandbox";
  underlying: string;
  phase_group: string | null;
  phase_no: number;
  status: TradeStatus;
  option_symbol: string;
  option_exchange: string;
  side: Side;
  option_type: OptionType;
  lots: number;
  lot_size: number;
  total_qty: number;
  entry_time: string | null;
  exit_time: string | null;
  entry_futures_price: number;
  entry_option_price: number;
  sl_price: number;
  sl_basis: string;
  sl_exit_option_price?: number | null;
  targets_total: number;
  targets_achieved: number[];
  targets: FrTradeTarget[];
  realized_pnl: number;
  remaining_qty: number;
  pnl_qty?: number;
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
  target_template_id?: number | null;
  trailing_mode?: TrailingMode;
}

export interface FrTemplateTarget {
  id: number;
  template_id: number;
  seq: number;
  points: number;
  exit_pct: number;
  enabled: boolean;
}

export interface FrTargetTemplate {
  id: number;
  name: string;
  description: string;
  is_default: boolean;
  enabled: boolean;
  targets: FrTemplateTarget[];
  created_at?: string | null;
  updated_at?: string | null;
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
  open_atm?: number | null;
  ce_default_strike?: number | null;
  pe_default_strike?: number | null;
  options_exchange: string;
}

export interface FrContractSettings {
  underlying: string;
  underlying_exchange?: string | null;
  expiry?: string | null;
  ce_strike?: number | null;
  pe_strike?: number | null;
  strike_selection_method?: StrikeSelectionMethod | null;
  moneyness_selection?: MoneynessSelection | null;
  lots: number;
  sl_points: number;
  product?: string | null;
  target_template_id?: number | null;
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
  strike_selection_method?: StrikeSelectionMethod;
  moneyness_selection?: MoneynessSelection;
  sl_points?: number | null;
  targets?: { points: number; exit_pct: number }[] | null;
  target_template_id?: number | null;
}
