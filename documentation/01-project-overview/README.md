# 1. Project Overview

## Product summary

OpenBull is a self-hosted options-trading and market-analysis platform for Indian markets. It presents one browser application, an OpenAlgo-compatible external REST API, authenticated live-market WebSockets, strategy and sandbox engines, and NinjaTrader integrations over broker-specific APIs.

The current repository supports these broker plugins: Angel One, Dhan, Fyers, Upstox, and Zerodha. Broker capabilities remain subject to the user's provider account, segment permissions, subscriptions, credentials, token lifetime, and rate limits.

## Primary capabilities

| Capability | Current implementation |
|---|---|
| Account and trading views | Dashboard, orders, trades, positions, holdings, symbol search |
| Options analytics | Option chain, OI tracker, max pain, Greeks, IV smile, volatility surface, straddle, GEX, straddle/strangle chain |
| Strategy design | Legacy Strategy Builder/Portfolio plus a separate lifecycle-based Strategy module |
| Futures-driven options risk | Draft/place/modify/exit workflows with futures-based targets, stop-loss, trailing, phase history, and NinjaTrader Quick Order |
| Simulation | Global live/sandbox mode and a tick-driven sandbox order, position, holding, margin, settlement, and P&L subsystem |
| External automation | `/api/v1/*`, strategy webhooks, WebSocket streaming, Bruno collection, .NET example, NinjaTrader add-ons |
| Operations | PostgreSQL, Redis cache-aside, rotating/DB logs, migrations, systemd/nginx/Certbot deployment scripts |

## Audience

- Developers extending backend, frontend, brokers, strategies, or integrations.
- Testers validating user workflows, permissions, APIs, real-time behavior, and releases.
- Administrators configuring brokers, sandbox, global trading mode, risk defaults, and logs.
- Operators deploying, monitoring, backing up, restoring, and troubleshooting the service.
- End users viewing data, using analytics, designing strategies, and placing permitted orders.

## Current role model

The current database has a boolean `users.is_admin`; it does not have tenants, tenant memberships, named roles, or granular permission tables. Initial `/setup` creates one admin and rejects a second setup. Server-side admin checks currently protect global trading-mode mutation, sandbox administration, error logs, selected API-log scope, analyzer toggle, and futures-risk administration.

Per-user ownership checks isolate broker credentials, API keys, saved strategies, strategy runs, and logs. The code contains non-admin behavior, but the repository does not provide an administrator-facing user-provisioning page or a tenant-admin role. See the [role and permission matrix](roles-and-permissions.md).

## System boundaries

OpenBull owns:

- Application authentication, sessions, encrypted broker configuration, user API keys, orders routed through the platform, sandbox state, strategy state, logs, and cached market data.
- Translation between the unified OpenBull contract and broker-specific contracts.
- Browser and integration behavior shipped in this repository.

External systems own:

- Broker accounts, trading/data subscriptions, exchange permissions, tokens, provider uptime, rate limits, and final live-order acceptance.
- DNS, TLS, firewall, proxy/CDN, host operating system, PostgreSQL, Redis, backup storage, and notification delivery configured outside this repository.
- NinjaTrader installation, licensing, instruments, historical database, workspaces, and third-party indicators.

## Important concepts

| Term | Meaning in this project |
|---|---|
| OpenBull session | HttpOnly-cookie browser session backed by a JWT and an `active_sessions` row. |
| OpenBull API key | Per-user key used by `/api/v1/*`, the market-data WebSocket authenticate message, NinjaTrader Quick Order, and other external clients. It is not a broker token. |
| Broker configuration | Long-lived app/client credentials and redirect data saved encrypted in `broker_configs`. |
| Broker authentication | Active broker access token saved encrypted in `broker_auth`; required by live broker requests and streaming. |
| Trading mode | Global `live` or `sandbox` mode stored in `app_settings`; admin-mutated and read by UI/API dispatch. |
| Master contract | Broker symbol/token catalogue normalized into `symtoken`. |
| MarketDataCache | Process-wide latest-tick store populated by the broker streaming adapter through the WebSocket proxy. |
| Strategy Builder | Saved multi-leg design and analytics feature under `/tools/strategybuilder`. |
| Strategy module | Separate scheduled/webhook-driven lifecycle system under `/strategy`. |
| Futures Risk | Options execution and phased risk management driven by an underlying futures price. |

## Navigation

- [Architecture](../02-system-architecture/README.md)
- [Frontend](../03-frontend/README.md)
- [Backend](../04-backend/README.md)
- [Database](../05-database/README.md)
- [API and WebSocket](../06-api-websocket/README.md)
- [Admin manual](../08-admin-user-manual/README.md)
- [End-user manual](../10-end-user-manual/README.md)
- [Operations](../11-deployment-operations/README.md)
