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

## Live exit safety and broker reconciliation

- Every SL, target, manual, partial, and emergency exit uses one persistent single-flight
  coordinator. Only one broker order can be in progress for a trade.
- Before a live exit, OpenBull reads a fresh broker position. A confirmed zero quantity
  closes the OpenBull phase without sending another order; API/auth/transport failures are
  never treated as zero.
- The background engine reconciles active trades after a short post-entry grace period.
  Broker snapshots are shared for five seconds so several cards do not flood the provider.
- A broker-confirmed rejection/non-submission enters `retry_wait`: the crossed level remains
  latched and OpenBull retries at most three times, ten seconds apart, after a fresh position
  verification. An exhausted target remains supersedable by the higher-priority risk limit.
- An uncertain submission enters the hard circuit breaker (`exit_state = blocked`). Automatic
  exits remain paused until **Verify broker & resume** confirms the live quantity. Ambiguous
  outcomes are never retried blindly.
- Target/RL evaluation accepts cached futures ticks for at most five seconds. A stale stream
  triggers one broker quote fallback and shares the refreshed price with the cache/UI.
- If the broker quantity is smaller (external partial close), OpenBull reduces its remaining
  quantity. An opposite-side or larger broker quantity is blocked for operator review.

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
| Exit-safety migration | `alembic/versions/20260722_fr_exit_safety.py` |
| Service (CRUD, resolve, place-trade) | `backend/futures_risk/service.py` |
| Broker reconciliation | `backend/futures_risk/reconciliation.py` |
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
