# Automated Strategy Lifecycle

## Purpose and access

The Strategy module defines scheduled batch strategies and signal-driven strategies, starts/stops runs, dispatches orders, applies risk rules, records checkpoints/events, and exposes a per-strategy WebSocket. All pages require an authenticated session and broker guard. Ownership is enforced by `user_id`; live enablement and destructive operations have additional server checks.

## Screenshots

- [Strategy list](../assets/screenshots/strategy-list/00-complete-page.png)
- [New strategy wizard](../assets/screenshots/strategy-wizard/00-complete-page.png)
- [01 — signal-driven fields](../assets/screenshots/strategy-wizard/01-signal-driven.png)
- [Saved strategy detail fixture](../assets/screenshots/strategy-detail/00-complete-page.png)
- [01 — Setup tab](../assets/screenshots/strategy-detail/01-setup-tab.png)
- [02 — Webhook tab](../assets/screenshots/strategy-detail/02-webhook-tab.png)
- [Saved strategy edit fixture](../assets/screenshots/strategy-edit/00-complete-page.png)
- [Strategy Portfolio fixture](../assets/screenshots/strategy-portfolio/00-complete-page.png)
- [01 — Expanded portfolio legs](../assets/screenshots/strategy-portfolio/01-expanded-strategy.png)
- [02 — Close strategy workflow](../assets/screenshots/strategy-portfolio/02-close-strategy.png)
- [03 — Delete strategy confirmation](../assets/screenshots/strategy-portfolio/03-delete-strategy-confirmation.png)

The saved fixture is explicitly named **Documentation NIFTY Spread**, is stopped, and never contacts a provider.

## Wizard controls and validation

| Area | Fields/rules |
|---|---|
| Identity/type | Name 1–200 chars; batch/time-driven or signal-driven kind; kind cannot be changed after creation. |
| Universe | Tab, underlying, exchange. MCX/stocks F&O expiry restrictions are validated. |
| Timing | Intraday requires entry and exit, and entry must precede exit; positional does not. |
| Product/price | CNC is cash-only; NRML derivatives-only; MIS may span supported intraday segments. |
| Legs | 1–10 unique positive IDs. Segment determines required option/futures/cash fields. |
| Signal legs | Symbol, exchange, side and absolute quantity required; futures/options also require supported expiry semantics. |
| Risk | Non-negative SL/target; lock-profit constraints; positive daily loss limit where supplied. |
| Scheduler | Enabled, selected weekdays, valid `HH:MM`, default Sandbox/Live mode. |
| Webhook | Allowlist entries are CIDR/label records; token plaintext is shown only by supported create/rotate response. |

## Create workflow

1. Open Strategies → New and choose batch or signal-driven behavior.
2. Complete identity/universe/type/product fields.
3. Add and validate every leg; the wizard changes fields according to strategy kind/segment.
4. Configure risk, scheduler and allowlist only as required.
5. Save and preserve any one-time webhook secret securely.
6. Reopen Detail and compare all saved values before enabling operation.

Expected result: a stopped `sm_strategy` owned by the current user. Creation does not automatically start or live-enable it.

## Operate and monitor

Start creates a run; Stop ends strategy processing according to backend state; Close All attempts to flatten strategy exposure; Kill activates the webhook kill-switch and safety path; Unlock is explicit. Live enablement is separate from global Live mode. Use Setup, Positions, Orders, Trades, Events, Risk, Webhook and History tabs; the REST snapshot and strategy WebSocket should converge on the same run/event state.

## Signal workflow

Send the documented action payload to the strategy-specific webhook URL. The handler verifies token hash, optional IP allowlist, lock state, live gates, direction, leg/symbol ownership and idempotency/state constraints. Inspect the event tab for accepted/rejected/ignored reasons; do not infer success from HTTP transport alone.

## Common errors

409 means editing/running state conflict; 403 may mean ownership, live gate, webhook lock or allowlist; 422 means strict schema validation (unknown fields are rejected); duplicate/invalid signals appear in event audit. A stopped strategy can still require broker-position reconciliation.

## APIs and dependencies

`/web/strategies`, strategy action/rotation/kill routes, `/webhook/strategy/{token}`, `/ws/strategy/{id}`, APScheduler, recovery/checkpoint/tick processor, event bus, PostgreSQL `sm_*` tables, broker/sandbox dispatch and market-data cache. See [Strategy real-time](../06-api-websocket/strategy-realtime.md).
