import type { FrEvent, FrPhase, FrTrade, FrTradeTarget, OptionType, Side, TradeStatus } from "@/types/futuresRisk";

interface DemoData {
  trades: FrTrade[];
  phases: FrPhase[];
  prices: Map<string, number>;
}

const instruments = [
  { underlying: "NIFTY", lotSize: 75, futuresBase: 23600, optionBase: 148, exchange: "NFO" },
  { underlying: "BANKNIFTY", lotSize: 35, futuresBase: 54100, optionBase: 312, exchange: "NFO" },
  { underlying: "FINNIFTY", lotSize: 65, futuresBase: 24850, optionBase: 124, exchange: "NFO" },
];

const statuses: TradeStatus[] = ["active", "draft", "completed", "stopped", "completed"];

function isoFrom(baseDate: Date, dayOffset: number, hour: number, minute: number) {
  const date = new Date(baseDate);
  date.setDate(date.getDate() - dayOffset);
  date.setHours(hour, minute, 0, 0);
  return date.toISOString();
}

function expiryCode(baseDate: Date) {
  const date = new Date(baseDate);
  date.setDate(date.getDate() + 16);
  return date
    .toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "2-digit" })
    .replace(/ /g, "")
    .toUpperCase();
}

function optionSymbol(underlying: string, expiry: string, strike: number, optionType: OptionType) {
  return `${underlying}${expiry}${strike}${optionType}`;
}

function buildTargets(entry: number, direction: number, lotSize: number, status: TradeStatus, hitCount: number): FrTradeTarget[] {
  const points = [50, 100, 150, 200];
  return points.map((targetPoints, index) => {
    const hit = index < hitCount;
    return {
      seq: index + 1,
      points: targetPoints,
      exit_pct: 25,
      trigger_price: entry + direction * targetPoints,
      exit_qty: lotSize,
      status: hit ? "hit" : status === "stopped" && index === hitCount ? "skipped" : "pending",
      hit_futures_price: hit ? entry + direction * (targetPoints + 4) : null,
      exit_order_id: hit ? `DEMO-T${index + 1}` : null,
      hit_at: null,
    };
  });
}

function buildEvents(trade: FrTrade): FrEvent[] {
  const rows: FrEvent[] = [
    {
      id: trade.id * 10 + 1,
      trade_id: trade.id,
      ts: trade.created_at,
      kind: trade.status === "draft" ? "draft_created" : "entry",
      severity: "info",
      message:
        trade.status === "draft"
          ? `Draft created for ${trade.option_symbol}`
          : `${trade.option_symbol} entered at futures ${trade.entry_futures_price}`,
      payload: null,
    },
  ];

  if (trade.status === "completed") {
    rows.push({
      id: trade.id * 10 + 2,
      trade_id: trade.id,
      ts: trade.closed_at,
      kind: "completed",
      severity: "info",
      message: "All planned target quantity exited",
      payload: null,
    });
  }

  if (trade.status === "stopped") {
    rows.push({
      id: trade.id * 10 + 3,
      trade_id: trade.id,
      ts: trade.closed_at,
      kind: "sl_hit",
      severity: "warning",
      message: `Stop-loss hit at futures ${trade.sl_price}`,
      payload: null,
    });
  }

  return rows;
}

function buildTrade(index: number, baseDate: Date): FrTrade {
  const dayOffset = index % 10;
  const instrument = instruments[index % instruments.length];
  const status = statuses[index % statuses.length];
  const optionType: OptionType = index % 2 === 0 ? "CE" : "PE";
  const side: Side = index % 3 === 0 ? "SELL" : "BUY";
  const direction = (optionType === "CE") === (side === "BUY") ? 1 : -1;
  const entryFutures = instrument.futuresBase + (index - 5) * 42;
  const strike = Math.round(entryFutures / 100) * 100;
  const lots = (index % 4) + 1;
  const totalQty = lots * instrument.lotSize;
  const hitCount = status === "completed" ? 4 : status === "stopped" ? index % 3 : status === "active" ? index % 2 : 0;
  const remainingQty = status === "active" || status === "draft" ? Math.max(instrument.lotSize, totalQty - hitCount * instrument.lotSize) : 0;
  const slPoints = 30 + (index % 3) * 5;
  const createdAt = isoFrom(baseDate, dayOffset, 9, 20 + (index % 5) * 5);
  const closedAt = status === "active" || status === "draft" ? null : isoFrom(baseDate, dayOffset, 14, 10 + index);
  const expiry = expiryCode(baseDate);

  const trade: FrTrade = {
    id: 9000 + index,
    mode: index % 2 === 0 ? "live" : "sandbox",
    underlying: instrument.underlying,
    option_symbol: optionSymbol(instrument.underlying, expiry, strike, optionType),
    option_exchange: instrument.exchange,
    option_type: optionType,
    side,
    product: "MIS",
    expiry,
    strike,
    lots,
    lot_size: instrument.lotSize,
    total_qty: totalQty,
    remaining_qty: remainingQty,
    entry_option_price: instrument.optionBase + index * 7,
    entry_order_id: status === "draft" ? null : `DEMO-ENTRY-${9000 + index}`,
    futures_symbol: `${instrument.underlying}${expiry}FUT`,
    futures_exchange: instrument.exchange,
    entry_futures_price: entryFutures,
    direction,
    sl_points: slPoints,
    sl_price: entryFutures - direction * slPoints,
    sl_basis: hitCount > 0 && status === "active" ? "entry" : "initial",
    status,
    realized_pnl: status === "completed" ? 1800 + index * 380 : status === "stopped" ? -900 - index * 140 : hitCount * 420,
    created_by: 1,
    modified_by: null,
    params: null,
    trailing_mode: index % 2 === 0 ? "entry_after_t1" : "prev_target",
    phase_group: `demo:${instrument.underlying}:${createdAt.slice(0, 10)}`,
    phase_no: (index % 3) + 1,
    closed_at: closedAt,
    duration_sec: status === "active" || status === "draft" ? null : 3600 + index * 420,
    created_at: createdAt,
    updated_at: closedAt ?? createdAt,
    targets: buildTargets(entryFutures, direction, instrument.lotSize, status, hitCount),
  };

  return { ...trade, events: buildEvents(trade) };
}

export function makeFuturesRiskDemoData(baseDate = new Date()): DemoData {
  const trades = Array.from({ length: 18 }, (_, index) => buildTrade(index, baseDate));
  const prices = new Map<string, number>(
    trades.flatMap((trade, index) => [
      [`${trade.futures_exchange}:${trade.futures_symbol}`, trade.entry_futures_price + trade.direction * (18 + index * 3)],
      [`${trade.option_exchange}:${trade.option_symbol}`, Math.max(1, trade.entry_option_price + (trade.side === "BUY" ? 1 : -1) * (6 + index))],
    ]),
  );
  const phases: FrPhase[] = trades
    .filter((trade) => trade.status !== "draft")
    .map((trade) => ({
      trade_id: trade.id,
      underlying: trade.underlying,
      phase_group: trade.phase_group,
      phase_no: trade.phase_no,
      status: trade.status,
      option_symbol: trade.option_symbol,
      side: trade.side,
      option_type: trade.option_type,
      lots: trade.lots,
      entry_time: trade.created_at,
      exit_time: trade.closed_at,
      entry_futures_price: trade.entry_futures_price,
      entry_option_price: trade.entry_option_price,
      sl_price: trade.sl_price,
      sl_basis: trade.sl_basis,
      targets_total: trade.targets.length,
      targets_achieved: trade.targets.filter((target) => target.status === "hit").map((target) => target.seq),
      realized_pnl: trade.realized_pnl,
      remaining_qty: trade.remaining_qty,
      duration_sec: trade.duration_sec,
      exit_kind: trade.status === "active" ? "open" : trade.status === "stopped" ? "auto" : trade.id % 2 === 0 ? "auto" : "manual",
    }));

  return { trades, phases, prices };
}
