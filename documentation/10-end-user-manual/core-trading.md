# Core Trading Workflows

## Purpose and access

Search, Order Book, Trade Book, Positions, and Holdings expose normalized broker/sandbox records. All require a browser session and active broker guard; write operations additionally use global mode and backend ownership/validation. There is no UI-only permission substitute.

## Screenshots

- [Search](../assets/screenshots/search/00-complete-page.png)
- [Order Book](../assets/screenshots/order-book/00-complete-page.png)
- [01 — Modify order](../assets/screenshots/order-book/01-modify-order.png)
- [02 — Cancel one confirmation](../assets/screenshots/order-book/02-cancel-order-confirmation.png)
- [03 — Cancel all confirmation](../assets/screenshots/order-book/03-cancel-all-confirmation.png)
- [Trade Book](../assets/screenshots/trade-book/00-complete-page.png)
- [Positions](../assets/screenshots/positions/00-complete-page.png)
- [01 — Close one confirmation](../assets/screenshots/positions/01-close-position-confirmation.png)
- [02 — Close all confirmation](../assets/screenshots/positions/02-close-all-confirmation.png)
- [Holdings](../assets/screenshots/holdings/00-complete-page.png)

The populated records are labelled, isolated sandbox fixtures. Action captures stop before the final mutation. Provider acknowledgements and exchange outcomes remain external evidence items.

## Controls and fields

| Area | Controls/data | Rules |
|---|---|---|
| Search | Query, exchange, result type, derivative builder, Copy/Try Search | Exact symbol must exist in current master contract. Builder requirements depend on equity/FUT/OPT selection. |
| Order Book | Sort, refresh, CSV, copy ID, Modify, Cancel, Cancel All | Availability depends on normalized order status. Destructive actions require confirmation. |
| Modify | Quantity, price type, price, trigger | MARKET uses neither; LIMIT requires price; SL-L requires price+trigger; SL-M requires trigger. Provider tick/order-state rules still apply. |
| Trade Book | Sort, refresh, CSV, identifiers | Read-only executed-trade view for selected mode. |
| Positions | LTP/P&L, sort, CSV, Close, Close All | Exit reverses current net quantity; recheck pending orders before repeating. |
| Holdings | Quantity, average/LTP/P&L totals, sort, CSV | Read-only delivery view; live overlays depend on quotes. |

## Search workflow

1. Select exchange/result type and enter a normalized search term.
2. For derivatives choose underlying, expiry and, for options, strike and CE/PE.
3. Select **Try Search**; do not assume a syntactically valid symbol is listed.
4. Copy the returned normalized symbol for API/strategy/NinjaTrader use.

Expected result: one or more current `symtoken` results. Empty results mean format, exchange, expiry, or contract-load state must be checked.

## Modify/cancel workflow

1. Confirm Live/Sandbox, symbol, side, quantity, price type, status, and order ID.
2. Select Modify or Cancel.
3. Enter only the fields required by the chosen price type.
4. Review and confirm.
5. Verify the HTTP result and refreshed normalized status. A request acknowledgement is not proof of exchange execution.

## Close-position workflow

1. Confirm symbol, exchange, product, net quantity, LTP and P&L.
2. Select **Close** or **Close All** and inspect the confirmation scope.
3. Submit once.
4. Check Order Book, Trade Book, then Positions until the final state is consistent.

Expected result: a reverse-side order for the remaining net quantity. If the first exit is pending, repeating it can reverse the position.

## Errors and troubleshooting

401/403 indicates application/API-key/broker authorization; 409 is a state conflict; 422 is field validation; broker rejection is returned in normalized message/data where possible. Stale P&L requires checking the exact quote subscription, market session, fallback quote request, and provider rate limits.

## APIs and dependencies

Browser routes under `/web` call orderbook/tradebook/positions/holdings/search services; external contracts live under `/api/v1`. All depend on PostgreSQL, selected mode, broker mapping, master contract, and—where prices are shown—market-data cache/WebSocket or quote fallback. See [endpoint inventory](../inventories/api-endpoints.md).
