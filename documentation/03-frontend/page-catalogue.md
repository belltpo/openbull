# Frontend Page Catalogue

This catalogue covers every route declared in `frontend/src/App.tsx`. “Broker required” means `ProtectedRoute requiresBroker`; it does not guarantee the provider token remains valid at request time. Backend permissions remain authoritative.

## Public and onboarding pages

### Home — `/`

- **Purpose:** Public product overview, capability highlights, and entry points.
- **Access:** Public. CTA changes to Dashboard for an authenticated user; otherwise Login/Get Started.
- **Source/dependencies:** `pages/Home.tsx`, auth context.
- **Controls:** Login/Get Started or Dashboard navigation; feature/stat sections.
- **Expected result:** Navigation only; no broker call.
- **Errors:** None beyond unavailable frontend assets/routing.
- **Screenshot:** [verified route state](../assets/screenshots/home/00-complete-page.png).

### Login — `/login`

- **Purpose:** Create an application session.
- **Access:** Public.
- **Fields/actions:** Username; password with visibility control; Sign In; conditional initial-setup link.
- **Validation:** Username/password required; server rate limits and credential verification are authoritative.
- **Expected result:** Dashboard when broker-authenticated, otherwise broker selection.
- **API:** `POST /auth/login`, `GET /auth/check-setup`, `GET /auth/me`.
- **Common errors:** Invalid credentials; rate limit; database unavailable; secure cookie misconfiguration.
- **Screenshot:** [verified route state](../assets/screenshots/login/00-complete-page.png).

### Initial Setup — `/setup`

- **Purpose:** Create the first administrator.
- **Access:** Public only while setup is required.
- **Fields/actions:** Username, email, password, confirm password, Create Account, Login link.
- **Validation:** All required; the current UI precheck allows six characters but the backend requires at least eight, so six- or seven-character values receive a server validation error. Confirmation must match; setup is rejected after any user exists.
- **Expected result:** Admin, API key, active session, then broker setup flow.
- **API:** `GET /auth/check-setup`, `POST /auth/setup`.
- **Screenshot:** [verified route state](../assets/screenshots/setup/00-complete-page.png).

### Not Found — `*`

- **Purpose:** Catch invalid frontend routes.
- **Access:** Public rendering.
- **Actions:** Return to Dashboard.
- **Screenshot:** [verified route state](../assets/screenshots/not-found/00-complete-page.png).

## Broker and integration credentials

### Select Broker — `/broker/select`

- **Purpose:** Choose and authenticate a configured broker.
- **Access:** Authenticated session.
- **Controls:** Broker cards; configured badge; declared exchanges; Configure; Login; Dhan access-token alternative.
- **Validation:** Broker configuration must exist; provider OAuth/internal login supplies remaining validation.
- **Expected result:** Active `broker_auth`, refreshed user context, and background master-contract download.
- **API:** `GET /web/broker/list`, `GET /auth/broker-redirect`.
- **Screenshot:** [verified route state](../assets/screenshots/broker-select/00-complete-page.png).

### Broker Configuration — `/broker/config`

- **Purpose:** Save encrypted broker application/client configuration.
- **Access:** Authenticated session.
- **Controls:** Broker selector; configured badge; provider-specific fields; password reveal controls; Save Credentials; Dhan alternate-token action.
- **Provider fields:** Upstox key/secret/redirect; Zerodha key/secret/redirect; Fyers App ID/secret/redirect; Dhan Client ID/App ID/App Secret/redirect; Angel SmartAPI key.
- **Validation:** Broker required. Initial required fields depend on broker. For an existing configuration, blank secret values preserve the saved encrypted value only where backend semantics permit.
- **Expected result:** “Broker credentials saved successfully”; this is not yet an active broker session.
- **API:** broker list, credential GET/PUT.
- **Screenshots:** [verified route state](../assets/screenshots/broker-config/00-complete-page.png); [01 — broker selector](../assets/screenshots/broker-config/01-open-broker-selector.png). Provider-filled variants require sanitized provider credentials and are not fabricated.

### Angel Login — `/broker/angel/totp`

- **Purpose:** Complete non-OAuth Angel SmartAPI login.
- **Fields:** Client Code, masked MPIN, six-digit numeric TOTP.
- **Validation:** All required; TOTP exactly six digits in UI.
- **API:** `POST /angel/login`.
- **Screenshot:** [verified route state](../assets/screenshots/broker-angel-totp/00-complete-page.png).

### Dhan Token Login — `/broker/dhan/token`

- **Purpose:** Alternate Dhan personal access-token login.
- **Fields:** Dhan Client ID and full token textarea.
- **Validation:** Client ID required; UI requires a token longer than 50 characters; backend applies its own full-token validation.
- **API:** `POST /auth/dhan/token-login`.
- **Screenshot:** [verified route state](../assets/screenshots/broker-dhan-token/00-complete-page.png).

### API Key — `/apikey`

- **Purpose:** Manage the per-user OpenBull integration key.
- **Controls:** Masked/last-four display; reveal for 30 seconds; copy; generate/rotate with warning.
- **Expected result:** New key works for `/api/v1` and market WebSocket; old integration values stop working after rotation.
- **API:** `GET/POST /web/apikey`.
- **Screenshot:** [verified route state](../assets/screenshots/api-key/00-complete-page.png); the key remains masked.

## Core application pages

### Dashboard — `/dashboard`

- **Purpose:** Combined account/trading/strategy overview.
- **Access:** Broker required.
- **Displayed data:** Cash/collateral/MTM/debits, day P&L, open positions, holdings, strategy counts, top positions, running strategies, recent orders/trades, market clock.
- **Controls:** Quick navigation/actions and refresh behavior from parallel queries.
- **Data refresh:** Source queries use feature-specific 15–60 second intervals plus query caching.
- **APIs:** Dashboard, positions, holdings, orderbook, tradebook, strategies.
- **Screenshot:** [verified route state](../assets/screenshots/dashboard/00-complete-page.png).

### Order Book — `/orderbook`

- **Purpose:** View and manage orders in current trading mode.
- **Controls:** Sort headers; CSV; copy order ID; modify; cancel; cancel all; confirmation dialogs.
- **Modify fields:** Quantity, price type, price, trigger price. MARKET/LIMIT/SL-L/SL-M combinations change required inputs.
- **Expected result:** Updated/cancelled order and refreshed table; broker/sandbox normalized message.
- **APIs:** web orderbook plus external modify/cancel/cancel-all operations.
- **Screenshots:** [populated order book](../assets/screenshots/order-book/00-complete-page.png); [01 — modify form](../assets/screenshots/order-book/01-modify-order.png); [02 — cancel one](../assets/screenshots/order-book/02-cancel-order-confirmation.png); [03 — cancel all](../assets/screenshots/order-book/03-cancel-all-confirmation.png). The fixture is sandbox-only and the confirmations are not submitted.

### Trade Book — `/tradebook`

- **Purpose:** View executed trades.
- **Controls:** Sort, refresh, CSV, copy identifiers.
- **Expected result:** Read-only normalized trade history for current mode.
- **Screenshot:** [verified route state](../assets/screenshots/trade-book/00-complete-page.png).

### Positions — `/positions`

- **Purpose:** Monitor open/net positions with live-price overlay and exit controls.
- **Controls:** Sort, CSV, close one, close all, confirmations.
- **Pricing:** Fresh WebSocket, multi-quote fallback, then REST/baseline where implemented.
- **Exit:** Reverse-side market action for remaining net quantity.
- **Screenshots:** [populated positions](../assets/screenshots/positions/00-complete-page.png); [01 — close one](../assets/screenshots/positions/01-close-position-confirmation.png); [02 — close all](../assets/screenshots/positions/02-close-all-confirmation.png). The fixture is sandbox-only and the confirmations are not submitted.

### Holdings — `/holdings`

- **Purpose:** View delivery holdings and portfolio totals with live overlay.
- **Controls:** Sort and CSV.
- **Screenshot:** [verified route state](../assets/screenshots/holdings/00-complete-page.png).

### Symbol Search — `/search`

- **Purpose:** Search current master contract and teach normalized symbol formats.
- **Controls:** URL-synced query, exchange and result tab, tokenized/debounced search, format guide, equity/future/option builder, expiry, strike, CE/PE, Copy, Try Search.
- **Validation:** Builder fields depend on instrument kind; exact symbol availability depends on master-contract data.
- **API:** symbol search, supported exchanges/underlyings.
- **Screenshot:** [verified route state](../assets/screenshots/search/00-complete-page.png). A populated builder workflow requires master-contract data.

### Logs — `/logs`

- **Purpose:** Inspect DB-backed API/error audit information.
- **Controls:** Statistics; free-text/API type/mode/status/date filters; five-second auto-refresh; cursor pagination; expandable request/response detail; export where exposed.
- **Permissions:** Non-admin API logs are restricted to own rows; error/global scope is admin-only server-side.
- **Screenshot:** [verified route state](../assets/screenshots/logs/00-complete-page.png); documentation fixtures contain no provider secrets.

### Sandbox — `/sandbox`

- **Purpose:** View simulator summary/configuration and perform simulator operations.
- **Controls:** Configuration cards; admin edit; personal reset; admin square-off, settlement, wipe/reload/reconcile actions with confirmations.
- **Permissions:** Standard user read-only for global config; admin for mutations; personal reset scope follows endpoint.
- **Screenshots:** [verified route state](../assets/screenshots/sandbox/00-complete-page.png); [01 — reset confirmation](../assets/screenshots/sandbox/01-reset-confirmation.png).

### Sandbox P&L — `/sandbox/mypnl`

- **Purpose:** Review up to 180 days of daily sandbox snapshots.
- **Data:** Cumulative realized, latest unrealized, trades, chart/table.
- **Screenshot:** [verified route state](../assets/screenshots/sandbox-pnl/00-complete-page.png).

## Developer/live-data pages

### WebSocket Test — `/websocket/test`

- **Purpose:** Diagnose market-data proxy, subscription, tick frames, and cache health.
- **Controls:** Connect/disconnect; symbol/exchange; LTP/Quote/Depth; subscribe/unsubscribe; frame log; backend health/cache.
- **Access:** Broker required but not in primary navigation.
- **Screenshot:** [verified route state](../assets/screenshots/websocket-test/00-complete-page.png).

### API Playground — `/playground`

- **Purpose:** Standalone REST and WebSocket workbench.
- **REST controls:** Endpoint search/catalog, tabs, method/path/query/body, API-key field, JSON validate/prettify/send, response status/timing/headers/body, cURL/copy.
- **WS controls:** Connection, authenticate/subscribe/unsubscribe/ping templates, composer, message log, latency.
- **Validation:** JSON must parse; operation still applies normal API auth/schema/mode/broker rules.
- **Screenshots:** [verified REST route state](../assets/screenshots/playground/00-complete-page.png); [01 — WebSocket mode](../assets/screenshots/playground/01-websocket-mode.png).

### Detached Quick Order — `/quick-order`

- **Purpose:** Browser detached futures-risk quick-order ticket.
- **Controls/validation:** Same underlying/expiry/strike/template/order rules as the futures-risk Quick Order component.
- **Screenshot:** [verified route state](../assets/screenshots/quick-order/00-complete-page.png).

## Analytics/tool pages

### Tools — `/tools`

- **Purpose:** Catalogue analytics and strategy tools.
- **Controls:** Eleven navigation cards. Futures Risk is reached through Positions/top-level navigation rather than this catalogue.
- **Screenshot:** [verified route state](../assets/screenshots/tools/00-complete-page.png).

### Option Chain — `/tools/optionchain`

- **Fields:** Exchange, underlying, expiry, strike count, persisted column chooser.
- **Output/actions:** REST chain plus Depth WebSocket merge; bid/ask launches order dialog.
- **Screenshot:** [verified route state](../assets/screenshots/option-chain/00-complete-page.png).

### OI Tracker — `/tools/oitracker`

- **Fields:** Exchange, underlying, expiry.
- **Output:** CE/PE open-interest chart.
- **Screenshot:** [verified route state](../assets/screenshots/oi-tracker/00-complete-page.png).

### Max Pain — `/tools/maxpain`

- **Fields:** Exchange, underlying, expiry.
- **Output:** Max-pain metrics and payout chart.
- **Screenshot:** [verified route state](../assets/screenshots/max-pain/00-complete-page.png).

### Option Greeks — `/tools/greeks`

- **Fields:** Exchange, underlying, expiry, interval, days, Load.
- **Tabs/output:** IV, Delta, Theta, Vega, Gamma; CE/PE historical charts.
- **Screenshot:** [verified route state](../assets/screenshots/option-greeks/00-complete-page.png).

### IV Smile — `/tools/ivsmile`

- **Fields:** Exchange, underlying, expiry, refresh controls.
- **Output:** Smile chart/table.
- **Screenshot:** [verified route state](../assets/screenshots/iv-smile/00-complete-page.png).

### Volatility Surface — `/tools/volsurface`

- **Fields:** Exchange, underlying, strikes around ATM, multiple expiries, Load.
- **Output:** Plotly 3D IV surface. First route load is large due to Plotly chunk size.
- **Screenshot:** [verified route state](../assets/screenshots/volatility-surface/00-complete-page.png).

### Straddle Chart — `/tools/straddle`

- **Fields:** Exchange, underlying, expiry, interval, days.
- **Toggles:** Straddle, spot, synthetic future series.
- **Screenshot:** [verified route state](../assets/screenshots/straddle/00-complete-page.png).

### GEX — `/tools/gex`

- **Fields:** Exchange, underlying, expiry, refresh.
- **Output:** Total/net gamma exposure charts and table.
- **Screenshot:** [verified route state](../assets/screenshots/gex/00-complete-page.png).

### Straddle/Strangle Chain — `/tools/straddles-strangle-chain`

- **Fields:** Strategy, index/stock, scrip, expiry, per-lot filters.
- **Output/actions:** Scanner matrix; Trade opens basket; active/recent baskets; Close/Add/reopen/discard.
- **Basket fields:** Product, Market/Limit/SL, included legs, quantity, price, margin, execute.
- **Screenshot:** [verified route state](../assets/screenshots/straddle-strangle-chain/00-complete-page.png).

### Strategy Builder — `/tools/strategybuilder`

- **Purpose:** Design/analyse/save/execute multi-leg option strategies.
- **Selectors/actions:** Exchange, underlying, expiry, template/load/save/order.
- **Leg fields:** Side, option type, strike, lots, entry; add/edit/delete.
- **Tabs:** Legs, Greeks, Payoff, Strategy Chart, Multi-Strike OI, P&L.
- **What-if:** Spot, IV, and days shifts.
- **Screenshot:** [verified route state](../assets/screenshots/strategy-builder/00-complete-page.png). Populated analytics/order dialogs require a resolved chain.

### Strategy Portfolio — `/tools/strategyportfolio`

- **Purpose:** Monitor/manage saved analytical strategies.
- **Filters/actions:** Live/sandbox/all; status; underlying; expand/view/close/delete.
- **Validation:** Close requires exit prices; delete confirmation.
- **Screenshots:** [populated portfolio](../assets/screenshots/strategy-portfolio/00-complete-page.png); [01 — expanded legs](../assets/screenshots/strategy-portfolio/01-expanded-strategy.png); [02 — close workflow](../assets/screenshots/strategy-portfolio/02-close-strategy.png); [03 — delete confirmation](../assets/screenshots/strategy-portfolio/03-delete-strategy-confirmation.png).

## Futures-risk pages

### Futures Risk — `/tools/futures-risk`

- **Purpose:** Manage phased options trades controlled by futures levels.
- **Summary:** Unrealized/realized P&L, active, drafts.
- **Tabs/filters:** Positions; Phase History; status; today/custom dates; position status.
- **Cards/actions:** Grouped instruments/phases; Modify; full/partial exit; Emergency; place/delete draft; timeline/history.
- **Quick Order fields:** Underlying, expiry, ATM/ITM-OTM/MANUAL/OFFSET method, moneyness or CE/PE strikes, lots ≥1, SL points, template/target overrides, product, draft, Buy/Sell CE/PE.
- **Data:** Four-second list polling plus active futures/options WebSocket.
- **Screenshots:** [verified route state](../assets/screenshots/futures-risk/00-complete-page.png); [01 — phase history](../assets/screenshots/futures-risk/01-phase-history.png); [02 — Quick Order](../assets/screenshots/futures-risk/02-quick-order.png). Modify/exit evidence requires a documentation-only active trade.

### Futures Risk Admin — `/tools/futures-risk/admin`

- **Purpose:** Global risk defaults, targets, and symbol mapping.
- **Access:** Route requires broker; page renders access denied for non-admin and backend enforces admin mutations.
- **Controls:** Default action/option/lots/SL/product; engine/trailing/mode/poll values; target template create/edit/default/delete; target levels and exit percentages; contract map resolve/add/update/delete.
- **Validation:** Enabled target exit percentages total 100%; positive points/quantities and mapping requirements enforced by UI/service.
- **Screenshot:** [complete admin page](../assets/screenshots/futures-risk-admin/00-complete-page.png). The current setup flow creates an admin; a non-admin provisioning workflow is not shipped.

### Futures Risk Card Demo — `/tools/futures-risk/card-demo`

- **Purpose:** Source-defined static responsive card design demonstration.
- **Access:** Broker required; not primary navigation; no API calls.
- **Status:** Internal/demo route, not a trading workflow.
- **Screenshots:** [verified route state](../assets/screenshots/futures-risk-card-demo/00-complete-page.png); [01 — expand all](../assets/screenshots/futures-risk-card-demo/01-expand-all.png).

## Strategy lifecycle pages

### Strategy List — `/strategy`

- **Purpose:** List scheduled/signal strategy definitions and current state.
- **Controls:** Status/mode/type/underlying/P&L/times; view; edit; delete; create.
- **Validation:** Edit/delete only when stopped.
- **Screenshot:** [verified route state](../assets/screenshots/strategy-list/00-complete-page.png).

### Strategy Wizard — `/strategy/new` and `/strategy/:id/edit`

- **Purpose:** Create or edit time/signal-driven multi-leg strategy definitions.
- **General fields:** Name, direction, universe, underlying, type, times, product, days/mode.
- **Time-leg fields:** Segment, expiry rank, lots 1–50, side, CE/PE, strike method/offset/value, SL, target, trailing.
- **Signal-leg fields:** Symbol, exchange, segment, expiry, side, quantity up to one million, optional option fields.
- **Risk fields:** Overall risk, trail-to-entry, lock-profit; schedule and live settings.
- **Limits/validation:** Maximum ten legs; required name and signal fields; server validates state/ownership.
- **Expected result:** Saved strategy; creation reveals webhook URL/token/body for signal mode.
- **Screenshots:** [complete batch wizard](../assets/screenshots/strategy-wizard/00-complete-page.png); [01 — signal-driven wizard](../assets/screenshots/strategy-wizard/01-signal-driven.png); [edit-route state](../assets/screenshots/strategy-edit/00-complete-page.png).

### Strategy Detail — `/strategy/:id`

- **Purpose:** Operate and audit one lifecycle strategy.
- **Actions:** Start sandbox/live, enable live with password, disable, kill, close all, stop, edit, delete.
- **Tabs:** Live, Setup, Positions, Orders, Trades, Events, Risk, Webhook, History.
- **Webhook:** Reveal/rotate token; enter/exit/close/reverse examples.
- **Validation:** Ownership; run state; lock/risk; destructive confirmations; live enabling and password rules.
- **Realtime:** Cookie-authenticated `/ws/strategy/{id}` snapshots/deltas/events.
- **Screenshots:** [populated strategy detail](../assets/screenshots/strategy-detail/00-complete-page.png); [01 — Setup tab](../assets/screenshots/strategy-detail/01-setup-tab.png); [02 — Webhook tab](../assets/screenshots/strategy-detail/02-webhook-tab.png). The webhook token is redacted in the fixture capture.
