# 4. Backend Documentation

## Stack and runtime

The backend is FastAPI on Python 3.12+, SQLAlchemy 2 async with asyncpg, PostgreSQL, Alembic, Pydantic settings/schemas, Redis asyncio, SlowAPI, HTTPX, APScheduler, ZeroMQ, and provider WebSocket libraries. Exact constraints are in `pyproject.toml` and exact resolved packages are in `uv.lock`.

## Endpoint families

| Family | Authentication | Purpose |
|---|---|---|
| `/auth/*` and broker callbacks | Public or current session depending on operation | Initial setup, login/logout/session, broker consent/token completion |
| `/web/*` and feature routers | HttpOnly session cookie | Browser application |
| `/api/v1/*` | OpenBull API key plus active broker context | Broker-neutral external API and NinjaTrader Quick Order |
| `/web/strategy/webhook/*` | Strategy webhook token | External strategy signals |
| `/ws/strategy/*` | Session cookie at handshake | Strategy-specific event stream |
| Market-data proxy `:8765`/production `/ws/` | Authenticate message with OpenBull API key | Live broker ticks |

See the generated [endpoint inventory](../inventories/api-endpoints.md).

## Core modules

- `main.py`: lifecycle, security/CORS middleware, route registration, health.
- `dependencies.py`: session, API-key, broker context, mode dispatch dependencies, cache invalidation.
- `security.py`: Argon2 password/API-key verification, Fernet encryption, JWT creation/validation.
- `middleware.py`: request ID and access logging.
- `middleware_api_log.py` and `utils/api_log_writer.py`: non-blocking authenticated request audit.
- `services/`: broker-neutral business operations and analytics.
- `broker/`: provider adapters and mappings.
- `sandbox/`, `futures_risk/`, `strategy/`: long-lived domain engines.

## Background work

See [background jobs and caching](background-jobs-and-caching.md). Jobs start in the single FastAPI process and include sandbox reconciliation/execution/scheduling/MTM, futures-risk auto-exit, strategy recovery/ticks/checkpoints/scheduling, API log persistence, master-contract download/cache refresh, and market-data health/reconnection.

## Error handling

- Domain `OpenBullException` instances use the shared exception handler.
- Validation errors use FastAPI/Pydantic responses.
- Request IDs are added to logs and responses for correlation.
- Broker modules return normalized success/error values which services translate to API responses.
- Sensitive values are redacted by centralized logging; new log statements must never interpolate raw credentials.

## Development rules

1. Keep router functions thin; place reusable domain logic in services/domains.
2. Enforce ownership and admin rules on the server.
3. Preserve live/sandbox dispatch parity for order and account operations.
4. Normalize provider data at the broker boundary.
5. Treat PostgreSQL as source of truth and Redis as discardable cache.
6. Add idempotent migrations for schema changes and tests for retry/concurrency/error behavior.
7. Avoid additional Uvicorn workers until singleton jobs/streams are externalized.

See [Security and Development Guidelines](security-and-development.md) before changing authentication, persistence, order dispatch, logging, deployment, or integration code.
