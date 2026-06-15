# Futures-Risk Options Module

Trade options; manage **target / stop-loss / trailing** entirely on the underlying
**futures** price, with automatic partial/full exits through OpenBull's order engine
(live broker e.g. Dhan, or the Sandbox simulator).

## How it works

1. **Place** an option order from the popup (Buy/Sell CE/PE) on the **Futures Risk** page.
2. At placement the module reads the **current-month futures price** for that underlying
   (from the admin symbol map) and snapshots a risk plan:
   - **Targets** at admin-configured points from entry (T1…Tn), each exiting an admin %.
   - **Stop-loss** at `entry ∓ sl_points`.
   - Direction is inferred: *Buy CE / Sell PE* are bullish (targets above, SL below);
     *Buy PE / Sell CE* are bearish (targets below, SL above).
3. A background engine polls the futures price (`poll_interval_sec`). When a level is hit it
   places a **reverse option order** for that slice via `order_service` (→ Dhan or Sandbox).
4. **Trailing**: after Target 1, the SL moves to **cost-to-cost (entry)** by default
   (`trailing_mode = entry_after_t1`); `prev_target` trails to the previous target instead.
5. The dashboard streams live futures + option LTP over the WS proxy and shows P&L, target
   status, remaining qty, and an auto-exit log per trade.

## UI

- **Dashboard** — `/tools/futures-risk`: active positions, entry/live futures, targets & SL
  status, remaining qty, real-time P&L, auto-exit logs, trade history.
- **Admin** — `/tools/futures-risk/admin` (admin only): risk settings, target-level CRUD,
  and underlying→futures **symbol-map CRUD** (NIFTY/BANKNIFTY seeded with auto-resolve;
  add stocks here).

## Backend

| Area | File |
|---|---|
| Tables (`fr_*`) | `backend/models/futures_risk.py` |
| Migration | `alembic/versions/20260611_futures_risk.py` |
| Service (CRUD, resolve, place-trade) | `backend/futures_risk/service.py` |
| Auto-exit engine (poll loop) | `backend/futures_risk/engine.py` |
| Order dispatch / broker ctx / events | `backend/futures_risk/execution.py` |
| Seed defaults | `backend/futures_risk/defaults.py` |
| Web API (`/web/fr/*`) | `backend/routers/futures_risk.py` |

Reuses `order_service` (Dhan + Sandbox dispatch), `option_symbol_service`,
`quotes_service`, and `MarketDataCache`. Engine started in the app lifespan.

## Notes

- **Develop in Sandbox mode** first (topbar toggle) — orders simulate while the futures
  price is still read live from the connected broker. Switch to Live to route real Dhan orders.
- A broker must be connected (for live prices); auto-resolve needs the master contract
  downloaded so the current-month FUT is in `symtoken`.
- Per-trade overrides (SL points, target points/%) are available in the order popup;
  otherwise the admin defaults apply.
