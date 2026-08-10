# Background Jobs, Scheduled Tasks, and Caching

## Job inventory

| Worker/job | Trigger | State touched | Failure behavior |
|---|---|---|---|
| API log writer | Authenticated HTTP requests enqueue rows | `api_logs` | Queue writer logs failures and bounds retained rows |
| Master-contract download | Successful broker login or explicit download | `symtoken`, in-process maps, Redis hashes | Runs in background thread; status endpoint reports progress/error |
| Sandbox catch-up | Application startup | Orders, positions, holdings, funds, daily P&L | Reconciles missed scheduled work before ticks resume |
| Sandbox execution engine | Market tick plus polling fallback | Sandbox orders/trades/positions/funds | Continues only for sandbox records; logs fill errors |
| Sandbox scheduler | Time-based loop | Square-off, settlement, resets | Persists last-run bookkeeping and retries later ticks |
| Sandbox MTM updater | Periodic | Open positions/funds/P&L | Uses latest tick/quote fallback |
| Futures-risk auto-exit | Periodic/tick-driven engine | `fr_trade`, targets/events/orders | Reconciles broker quantity, applies target/SL/trailing through a persistent single-flight exit, retries only broker-confirmed non-execution with bounded backoff, and hard-blocks ambiguous outcomes |
| Strategy recovery | Startup | Active runs/checkpoints | Restores active strategy state before scheduler starts |
| Strategy tick processor/feed | MarketDataCache subscriber | Runs/orders/events/checkpoints | Queue isolates tick ingestion from processing |
| Strategy checkpoint | Periodic (default source interval is five seconds) | `sm_strategy_checkpoint` and run state | Logs failed passes and retries next interval |
| Strategy scheduler | APScheduler jobs | Strategy runs/events | Syncs enabled schedules in Asia/Kolkata timezone |
| WebSocket health/reconnect | Continuous | Adapter, subscriptions, MarketDataCache health | Replaces unhealthy adapters and replays pooled demand |

## Cache inventory

| Cache | Scope | Source of truth | Invalidation/fallback |
|---|---|---|---|
| API-key validity | Redis TTL | `api_keys` | Rotation/logout invalidation; DB verification on miss |
| Broker/API context | Redis TTL | `broker_auth`, `broker_configs` | Re-auth/logout invalidation; DB/decrypt on miss |
| Symbol/token maps | Process maps and Redis hashes | `symtoken` | Rebuilt after master-contract download/startup |
| Latest market data | Process-wide `MarketDataCache` | Broker live stream | REST quote fallback where implemented; marked stale after inactivity |
| Trading mode | Short in-process cache | `app_settings` | Invalidated after admin mutation |
| Quote request coalescing | Process-level cache/single-flight | Broker quote API | Short TTL, broker/rate-limit backoff |
| Futures-risk position snapshot | Process-level five-second cache per broker session | Broker positions API | Forced fresh read before every exit; invalidated after an order; errors fail closed |

Redis client pools are owned per asyncio event loop because background threads may use their own temporary event loops. Code running in a thread must not reuse a client bound to FastAPI's loop.

## Operational implications

- Redis loss should degrade to DB/in-process behavior, but timeouts or loop-ownership bugs can increase latency; monitor Redis warnings.
- A stale broker access token affects REST quote fallback and the shared live adapter, so multiple pages/integrations can fail together.
- Restarting the single service restarts every in-process worker; startup catch-up must finish before trusting state.
- Scheduled times are interpreted in Asia/Kolkata unless a module explicitly records otherwise.
