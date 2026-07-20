# Folder and File Structure

```text
openbull/
├── alembic/                     Database migration environment and revisions
├── backend/
│   ├── api/                     External `/api/v1` API-key endpoints
│   ├── broker/                  Five provider plugins
│   ├── events/, subscribers/    In-process event definitions and consumers
│   ├── futures_risk/            Futures-driven option risk domain
│   ├── models/                  SQLAlchemy tables
│   ├── routers/                 Browser/session web endpoints
│   ├── sandbox/                 Simulated execution, holdings, settlement, P&L
│   ├── schemas/                 Pydantic request/response contracts
│   ├── services/                Broker-neutral business and analytics services
│   ├── strategy/                Strategy lifecycle engine, scheduler, webhook logic
│   ├── test/                    Backend unit/integration-style tests
│   ├── utils/                   Logging, Redis, HTTP, plugins, migrations, event bus
│   ├── websocket_proxy/         Authenticated pooled market-data proxy
│   ├── config.py                Pydantic environment settings
│   ├── database.py              Async/sync database factories and ORM Base
│   ├── dependencies.py          Session/API-key/broker dependencies and caches
│   ├── main.py                  App, middleware, routers, startup/shutdown
│   └── security.py              Password, JWT, API-key, and encryption functions
├── collections/openbull/        Bruno REST/WebSocket examples
├── docs/                        Legacy design/API notes retained for compatibility
├── documentation/               Maintained full documentation set
├── frontend/
│   ├── public/                  Static public assets
│   └── src/
│       ├── api/                 Typed Axios wrappers by feature
│       ├── components/          Layout, UI, trading, charts, strategy, risk
│       ├── contexts/            Authentication, theme, trading mode
│       ├── hooks/               Market data, visibility, strategy, chain state
│       ├── lib/                 Pricing, CSV, templates, formatting utilities
│       ├── pages/               Route-level pages
│       ├── types/               TypeScript domain contracts
│       ├── App.tsx              Provider composition and route table
│       └── main.tsx             React bootstrap
├── install/                     Fresh install, update, performance tuning scripts
├── integrations/ninjatrader/    Quick Order, drawing bridge, live-data add-on/feed
├── sdk-dotnet/                  .NET external API example
├── .env.example                 Safe local configuration template
├── install.sh                   Supported interactive production entry point
├── migrate_all.py               Idempotent migration orchestrator
├── pyproject.toml, uv.lock      Python dependencies/lock
├── run-local.bat, RUN_LOCAL.txt Windows local run helpers
└── sandbox_e2e_test.py          End-to-end sandbox validation script
```

## Broker plugin layout

Each `backend/broker/<broker>/` contains provider-specific `api`, `database`, `mapping`, and `streaming` modules plus `plugin.json`. Common services load the active broker module dynamically; provider code must return normalized OpenBull results rather than leaking provider-specific contracts upward.

## Two strategy areas

The repository contains two distinct implementations that must not be confused:

- `backend/models/strategies.py`, `routers/strategies.py`, and strategy-builder services support saved analytical multi-leg designs and the `/tools/strategybuilder`/`strategyportfolio` pages.
- `backend/models/strategy_module.py`, `backend/strategy/`, and `routers/strategy_module.py` support scheduled/webhook-driven strategy runs, orders, checkpoints, events, and the `/strategy` pages.
