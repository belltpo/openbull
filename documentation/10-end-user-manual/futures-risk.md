# Futures Risk and Quick Order

## Purpose and access

Futures Risk manages option phases whose stop, targets and trailing levels are driven by the underlying futures price while option premium drives MTM/P&L. The web page requires an authenticated session and active broker guard. Admin mutation controls live under the Admin page; API-key clients such as NinjaTrader use the external Futures Risk routes.

## Screenshots

- [Futures Risk positions state](../assets/screenshots/futures-risk/00-complete-page.png)
- [01 — Phase history](../assets/screenshots/futures-risk/01-phase-history.png)
- [02 — Quick Order dialog](../assets/screenshots/futures-risk/02-quick-order.png)
- [Futures Risk Admin](../assets/screenshots/futures-risk-admin/00-complete-page.png)
- [Card demo](../assets/screenshots/futures-risk-card-demo/00-complete-page.png) and [01 — expanded](../assets/screenshots/futures-risk-card-demo/01-expand-all.png)

The card-demo route uses source-defined demo data. It is visual evidence, not an executed trade.

## Quick Order fields

| Field/control | Meaning/rule |
|---|---|
| Underlying/expiry | Resolve current futures and option universe from Futures Risk configuration/master contract. |
| Strike method | ATM nearest configured step; ITM/OTM moneyness selection; MANUAL explicit CE/PE; OFFSET configured offsets. |
| Lots | Positive lot count; final quantity uses current instrument lot size. |
| SL points | Futures-distance input; must satisfy configured validation. |
| Template/targets | Target count, distances and exit percentages; percentages/remaining quantity must form a valid execution plan. |
| Product | Broker/sandbox product such as MIS according to enabled configuration. |
| Buy/Sell CE/PE | Places or drafts the selected option direction after preview. |
| Modify/Close/Partial/Emergency | Mutates only the owned active phase and requires confirmation/state validation. |

## Place and manage workflow

1. Confirm Live/Sandbox and open Quick Order.
2. Choose underlying/expiry/strike method, then inspect resolved futures, CE and PE symbols/prices.
3. Set lots, SL and target template; use preview to catch missing mappings/LTP before ordering.
4. Submit once and verify the new phase identifier/card.
5. Monitor futures level, option premium, remaining quantity, event milestones and phase MTM.
6. Modify only permitted future-driven levels. Use partial/full/emergency exit with explicit scope.
7. Reconcile phase state with Order Book/Trade Book/Positions and the phase event history.

If a position is closed or partially closed directly in the broker terminal, OpenBull
periodically reconciles the broker quantity. A confirmed zero closes the phase without a
new order. A broker-confirmed rejection is retried with a bounded cooldown after a fresh
position check; the crossed target stays latched while waiting. If the retry limit is reached,
or an exit result is uncertain, the card shows the applicable warning. Use **Verify broker &
resume** once; it refreshes the broker position first, closes an already-flat phase, adjusts an
external partial close, or resumes protection only when the direction/quantity is safe.

## Calculations and expected result

Futures values determine level hits. Option entry/current/exit price multiplied by executed/remaining quantities determines option MTM and booked P&L. Therefore a futures target hit does not itself guarantee positive option P&L. Successful closure records exit quantities/prices/events and moves the phase into history.

## Validation and errors

An underlying may reject a second phase while one is active (409). Missing futures/option LTP blocks market pricing. Invalid token/API key returns 401; provider/session gates return 403; invalid template/levels return 4xx. A 409 mentioning exit protection means the first exit result requires broker verification; do not repeatedly click Close/Emergency. Rate-limit errors require cooldown, not aggressive retry. Zero P&L must be checked against actual option entry/exit prices and executed quantity.

## NinjaTrader relationship

Quick Order polls preview/trade/detail endpoints using the OpenBull API key. Multiple chart instances can use separate instrument settings; server phase limits remain shared. Dhan live-data AddOn and Quick Order are independent clients but converge on the same OpenBull backend/provider state.

## APIs and dependencies

`/web/futures-risk/*`, `/api/v1/futures-risk/quick-order*`, trade detail/list/levels/exit, Futures Risk service/engine/defaults, sandbox or live execution, market-data cache, master contract, Dhan/broker REST+WS and NinjaTrader integration.
