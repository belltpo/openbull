# 6. API and WebSocket Documentation

## Contracts

- [Generated endpoint inventory](../inventories/api-endpoints.md)
- [Generated OpenAPI document](../inventories/openapi.json)
- [API request/response reference guide](api-reference-guide.md)
- [Authentication and errors](authentication-and-errors.md)
- [Market-data WebSocket protocol](websocket-protocol.md)
- [Strategy WebSocket and webhooks](strategy-realtime.md)
- The [standalone generated endpoint guides](external-api/README.md) mirror and redact the detailed `docs/api/` examples; executable Bruno requests remain under `collections/openbull/`.

## API surfaces

### Browser/session API

The React SPA calls same-origin endpoints with an HttpOnly cookie. These endpoints manage setup, sessions, brokers, pages, logs, sandbox, saved strategies, strategy lifecycle, and futures-risk administration.

### External API

`/api/v1/*` operations use an OpenBull API key, normally in the JSON body as `apikey`. The dependency resolves the owning user and active broker context. Request and response structures are described by OpenAPI/Pydantic and executable Bruno requests.

### Health

`GET /health` returns application name, status, and version from FastAPI. In production, verify nginx actually proxies this path to FastAPI; an SPA fallback returning HTML is not a backend health response.

## Request conventions

- JSON is the default request/response representation.
- OpenAlgo-compatible symbols are uppercase normalized symbols such as an underlying, dated future, or dated option; exact formats and broker mappings are covered in the symbol guide.
- Exchange, product, action, and price-type values are validated by schemas/services and provider support.
- Sandbox and live use the same external endpoint family; global trading mode selects the dispatcher.
- Every HTTP response is correlated with request logging; use the request ID when troubleshooting.

## Response conventions

External operations generally return a top-level status plus normalized data or a message. Browser routers often return typed resources. Consumers must use the OpenAPI contract for the specific operation and must not assume every endpoint uses an identical envelope.
