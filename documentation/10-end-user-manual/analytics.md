# Analytics Tools

## Purpose and access

Analytics pages transform broker quotes, option chains, OI, Greeks and historical candles into decision-support views. They require an authenticated session and active broker guard. They do not place an order unless the user explicitly enters an associated basket/order workflow.

## Screenshots and controls

| Tool | Screenshot | Required selectors | Principal output |
|---|---|---|---|
| Option Chain | [page](../assets/screenshots/option-chain/00-complete-page.png) | exchange, underlying, expiry, strike range | CE/PE chain and live merged fields |
| OI Tracker | [page](../assets/screenshots/oi-tracker/00-complete-page.png) | exchange, underlying, expiry | CE/PE OI series |
| Max Pain | [page](../assets/screenshots/max-pain/00-complete-page.png) | exchange, underlying, expiry | payout curve/max-pain strike |
| Option Greeks | [page](../assets/screenshots/option-greeks/00-complete-page.png) | exchange, underlying, expiry, interval/days | IV/Delta/Theta/Vega/Gamma history |
| IV Smile | [page](../assets/screenshots/iv-smile/00-complete-page.png) | exchange, underlying, expiry | strike IV smile/table |
| Vol Surface | [page](../assets/screenshots/volatility-surface/00-complete-page.png) | exchange, underlying, ATM range, expiries | 3-D IV surface |
| Straddle | [page](../assets/screenshots/straddle/00-complete-page.png) | exchange, underlying, expiry, interval/days | premium/spot/synthetic series |
| GEX | [page](../assets/screenshots/gex/00-complete-page.png) | exchange, underlying, expiry | exposure profile/totals |
| Straddle/Strangle Chain | [page](../assets/screenshots/straddle-strangle-chain/00-complete-page.png) | strategy, scrip, expiry filters | scan and basket candidate |

## Workflow

1. Confirm broker authentication and completed master contract.
2. Select exchange before underlying; then choose an expiry returned by the application.
3. Set interval/days/strike range only where exposed.
4. Load/refresh and inspect result timestamp and source selectors.
5. Cross-check missing/zero values against chain liquidity and provider data rather than treating zero as automatically valid.
6. If moving to a basket/order workflow, revalidate every generated leg, quantity, price type, mode, and margin result.

## Validation and expected results

Selectors must resolve to current contracts. Intervals/date spans are constrained by endpoint schemas and provider limits. Successful output is a timestamped chart/table; it is not an exchange guarantee. Bidless contracts, incomplete OI, insufficient history, invalid IV inputs, or rate limiting can yield sparse/empty results.

## Common errors

- No expiry/chain: check exchange/underlying/master contract/provider segment.
- REST chain works but live cells do not: check WebSocket auth/subscriptions/cache freshness.
- Greeks/IV missing: check valid price, spot, strike, expiry time, and risk-free assumptions.
- HTTP 429/805 upstream: stop rapid refresh; allow configured backoff/cooldown.
- Different values across tools: compare timestamps, symbol/exchange, interval and data source.

## APIs and dependencies

Relevant `/api/v1` operations include optionchain, OI tracker, max pain, option greeks, IV smile/chart, vol surface, straddle, GEX, history, expiry, symbol and quotes. Computation services depend on broker mappings, master contract, HTTP client, quote cache and (for live merges) WebSocket market-data cache.
