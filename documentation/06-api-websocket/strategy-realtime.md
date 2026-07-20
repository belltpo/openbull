# Strategy WebSocket and Webhooks

The strategy lifecycle module has a separate real-time channel from the broker market-data proxy.

## Strategy WebSocket

`/ws/strategy/{strategy_id}` uses the browser session cookie during the handshake. The server verifies strategy ownership and closes unauthorized or cross-owner connections. It broadcasts strategy/run/order/event updates so detail pages do not need aggressive polling.

## Strategy webhook

`POST /web/strategy/webhook/{webhook_token}` uses a rotated per-strategy token rather than a browser cookie. The webhook handler validates:

- Token ownership and active strategy.
- Payload/action schema.
- Idempotency/replay and event state.
- Strategy schedule/run/lock state.
- Live-mode enablement and risk policy.
- Permitted transitions and order dispatch.

Webhook tokens are secrets. Rotate them through the authenticated strategy endpoint and update the external sender immediately.

## Separation from market data

Strategy event WebSockets carry application lifecycle events. Market prices continue to arrive through the unified market-data proxy and `MarketDataCache`; the two protocols are not interchangeable.
