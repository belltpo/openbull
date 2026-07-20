# Market-Data WebSocket Protocol

## Endpoint and authentication

Local development uses the configured WebSocket URL, normally `ws://127.0.0.1:8765`. Production nginx exposes `/ws/` over `wss://` and proxies to port 8765.

After connection, send:

```json
{"action":"authenticate","api_key":"<OPENBULL_API_KEY>","request_id":"auth-1"}
```

The key resolves the user, active broker token, broker name, and broker configuration. It is not a Dhan/Upstox/etc. token.

## Subscribe

```json
{
  "action": "subscribe",
  "mode": "LTP",
  "request_id": "sub-1",
  "symbols": [
    {"exchange": "NSE_INDEX", "symbol": "NIFTY"}
  ]
}
```

Supported normalized modes are `LTP`, `QUOTE`, and `DEPTH` (`FULL` is accepted as depth by the proxy mapping). The proxy tracks client demand and subscribes upstream once per exchange/symbol at the highest requested mode.

## Unsubscribe

Send the same symbol list with `action: "unsubscribe"` and the applicable mode. Disconnect cleanup removes that client's demand and adjusts pooled upstream subscriptions.

## Market-data message

Normalized messages have type `market_data`, exchange, symbol, mode/provider metadata as available, and a `data` object. Depending on mode/provider, data may include LTP, OHLC, volume, OI, bid/ask, totals, last quantity/time, and depth arrays. Consumers must treat fields as optional because provider entitlements and modes differ.

## Reliability behavior

- Browser hooks reconnect with exponential backoff, reauthenticate, and replay desired symbols.
- The server fingerprints broker/token/client context and replaces stale or unhealthy adapters.
- Pooled subscription demand is replayed after adapter replacement.
- Broker-auth-required issues close authenticated clients with a broker-action reason.
- `MarketDataCache` records connection/data freshness and exposes authenticated health endpoints.

## Limits in current proxy

- Ten concurrent downstream clients.
- 64 KiB maximum inbound message size.
- One thousand symbols per downstream subscribe message.
- Upstream provider limits may be lower and are handled by broker adapters/batching.

## Diagnostic sequence

1. Verify `/api/websocket/config` and `/api/websocket/apikey` with a valid browser session.
2. Verify the public `wss://.../ws/` handshake.
3. Verify authentication acknowledgement.
4. Verify subscribe acknowledgement.
5. Check logs for adapter connection and batch subscription.
6. Check `/api/websocket/health` for authentication, data age, cache size, and subscribers.
7. Distinguish an open socket with no exchange ticks from an authentication/subscription failure.
