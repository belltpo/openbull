# API Request and Response Reference Guide

## Authoritative artifacts

The current application exposes 166 operations over 148 OpenAPI paths. No hand-maintained table should duplicate those contracts and drift. Use these artifacts together:

1. [Generated endpoint inventory](../inventories/api-endpoints.md) — method, path, operation, classified authentication, parameters/body schema, and success schema.
2. [Generated OpenAPI JSON](../inventories/openapi.json) — machine-readable request bodies, parameters, status responses, and component schemas emitted by the current FastAPI application.
3. [Generated external API guide set](external-api/README.md) — standalone, redacted copies of all 41 detailed request/response/field guides maintained in `docs/api/`.
4. `collections/openbull/` — executable Bruno request bodies for the OpenAlgo-compatible API.

When OpenAPI shows no request schema, the endpoint currently accepts an untyped/raw body. In that case the endpoint implementation and Bruno body are authoritative; this is also a candidate for adding a Pydantic request model.

## Base URLs

| Environment | HTTP base | Market-data WebSocket |
|---|---|---|
| Local | `http://127.0.0.1:8000` | `ws://127.0.0.1:8765` |
| Production | `https://YOUR_DOMAIN` | `wss://YOUR_DOMAIN/ws` |

The browser normally uses same-origin relative URLs through Vite (local) or nginx (production).

## External API request pattern

```http
POST /api/v1/quotes HTTP/1.1
Content-Type: application/json

{
  "apikey": "${OPENBULL_API_KEY}",
  "symbol": "SYMBOL_IN_OPENBULL_FORMAT",
  "exchange": "EXCHANGE_CODE"
}
```

Never include the key in a URL. Some dependencies also accept the `X-API-KEY` header, but clients should follow the contract shown for the specific endpoint/collection.

Successful external operations normally return a normalized `status` and `data` or an order/message field. Error shapes vary between FastAPI validation, OpenBull domain errors, and normalized provider errors, so clients must handle HTTP status plus JSON content rather than checking only a `status` string.

## Endpoint families and detailed source indexes

| Family | Main operations | Detailed field documentation |
|---|---|---|
| Account | funds, holdings, margin, orders, positions, trades | [Account services](external-api/account-services/funds.md) |
| Order management | place/smart/options/basket/split/modify/cancel/close | [Order management](external-api/order-management/placeorder.md) |
| Order information | status, open position | [Order information](external-api/order-information/orderstatus.md) |
| Market data | quote, multi-quote, depth, history, intervals | [Market data](external-api/market-data/quotes.md) |
| Symbols/options | search, symbol, expiry, option symbol/chain/Greeks/synthetic future | [Symbol](external-api/symbol-services/search.md) and [options](external-api/options-services/optionchain.md) services |
| Analytics | GEX, IV chart/smile, max pain, OI tracker, straddle, volatility surface | [Analytics](external-api/analytics-tools/gex.md) |
| Futures Risk | quick-order settings/options/preview/place and trade detail/levels/exit | OpenAPI plus `backend/api/futures_risk.py` |
| Browser features | auth, broker configuration, logs, sandbox, strategies, admin | OpenAPI plus `frontend/src/api/` callers |

## Authentication examples

### Browser/session endpoint

```http
GET /auth/me HTTP/1.1
Cookie: access_token=<HttpOnly cookie managed by browser>
```

JavaScript must not read or manually copy the cookie. The shared Axios client sends credentials.

### Strategy webhook

The generated OpenAPI and strategy detail page show the exact route/body for a created strategy. The strategy-specific webhook token grants signal submission only; it is not an OpenBull account API key.

### WebSocket

Market-data WebSocket authentication and subscribe payloads are documented in [websocket-protocol.md](websocket-protocol.md). Strategy WebSockets use the session cookie and are documented in [strategy-realtime.md](strategy-realtime.md).

## Contract change procedure

1. Change Pydantic schema/route and implementation together.
2. Update frontend/API/SDK consumers and Bruno examples.
3. Add compatibility and validation tests.
4. Regenerate inventories with `documentation/tools/generate_reference.py`.
5. Run `documentation/tools/validate_documentation.py`.
6. Record breaking/additive behavior in the documentation change log and release notes.
