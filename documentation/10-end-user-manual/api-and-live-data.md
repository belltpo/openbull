# API Playground and Live-Data Diagnostics

## Purpose and access

Playground exercises external REST/WebSocket contracts; WebSocket Test isolates broker streaming, subscription and cache health. Both require a browser session; WebSocket Test also uses the broker guard. The OpenBull API key is separate from the browser cookie and broker token.

## Screenshots

- [REST Playground](../assets/screenshots/playground/00-complete-page.png)
- [01 — WebSocket Playground](../assets/screenshots/playground/01-websocket-mode.png)
- [WebSocket Test](../assets/screenshots/websocket-test/00-complete-page.png)
- [API-key management](../assets/screenshots/api-key/00-complete-page.png)

## Controls

REST mode provides endpoint search/catalog, method/path/query/body editor, API-key input, JSON validation/format, Send, status/timing/headers/body and cURL/copy. WebSocket mode provides URL, Connect, auto-reconnect, message templates, composer, Send and frame log. WebSocket Test adds exact exchange/symbol, LTP/QUOTE/DEPTH, subscribe/unsubscribe, frames and backend health/cache.

## REST workflow

1. Generate/copy the current OpenBull API key from API Key; rotating invalidates existing clients.
2. Select an operation and review its method/path/schema in the generated API reference.
3. Enter required query/body values, validate JSON, and confirm global mode for writes.
4. Send once and inspect HTTP status plus normalized response, not only a green UI state.
5. Redact API keys/tokens before copying cURL into tickets or documentation.

## WebSocket workflow

1. Connect to the deployment's supported WebSocket URL.
2. Send `authenticate` with the OpenBull API key and wait for acknowledgement.
3. Subscribe with exact exchange/symbol and LTP, QUOTE or DEPTH mode.
4. Confirm subscription acknowledgement, then check frame timestamps/content.
5. Compare WebSocket Test cache health if no ticks arrive.
6. Unsubscribe/disconnect after testing.

## Expected result and errors

| State | Interpretation/action |
|---|---|
| Connection cannot open | Check scheme/TLS/nginx/path/port/backend proxy. |
| Authentication fails | Check current OpenBull key and active broker session/context. |
| Subscribe rejected | Check message schema, symbol limit, exchange/symbol and adapter support. |
| Subscribed/no tick | Check exact mapping, entitlement, provider socket, market session and instrument activity. |
| REST quote works/WS fails | Diagnose adapter/subscription/proxy path. |
| WS works/analytics empty | Diagnose analytics request/history/input rather than socket. |
| Frequent reconnect/stale feed | Inspect Dhan/provider close reason, backoff, one-worker ownership, Redis/cache and network stability. |

## Validation, security and dependencies

JSON must parse; schemas reject missing/extra fields as defined. Never put API keys in URLs, Git, screenshots or logs. External API operations typically require API key plus active broker context; the documented Futures Risk trade list/detail reads require only API-key owner identity. Dependencies include nginx WebSocket upgrade, in-process proxy, provider adapter, ZMQ, market-data cache, Redis fallback and exact master-contract mapping.
