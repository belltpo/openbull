# Strategy Builder and Portfolio

## Purpose and access

Strategy Builder models multi-leg option/futures structures, payoff, Greeks, history and what-if changes. Strategy Portfolio stores analytical strategies and supports closing/deleting its records. Both require an authenticated session and active broker guard. Basket execution follows global mode and backend broker/sandbox validation.

## Screenshots

- [Strategy Builder complete route state](../assets/screenshots/strategy-builder/00-complete-page.png)
- [Strategy Portfolio](../assets/screenshots/strategy-portfolio/00-complete-page.png)

## Builder fields and controls

| Area | Controls | Meaning/validation |
|---|---|---|
| Underlying header | exchange, underlying, expiry | Drives chain, spot/future context and contract choices; must exist in master contract. |
| Template/legs | template, add/edit/delete leg | A leg records side, type, strike, lots and price context. Review generated values before saving. |
| Leg dialog | BUY/SELL, CE/PE/FUT, strike, lots, price | Quantity derives from current lot size. Prices/triggers must meet provider tick rules at order time. |
| Payoff/Greeks | chart, break-evens, max profit/loss, Greeks | Analytical estimates from current inputs; not guaranteed fills. |
| What-if | spot, IV, days | Recalculates scenario only; does not alter broker positions. |
| Data tabs | chart, multi-strike OI, P&L | Availability depends on history/quotes/chain. |
| Save/load | name, Save, saved-strategy picker | Persists analytical record; name/leg validity enforced by API. |
| Basket | product, price type, margin, execute | Explicit order workflow; partial per-leg success is possible. |

## Build and save workflow

1. Select exchange, underlying and an available expiry.
2. Choose a template or add legs manually.
3. Verify each side, instrument type, strike, lots and reference price.
4. Review payoff and Greeks; change what-if inputs to understand sensitivity.
5. Check chart/OI/P&L tabs only after confirming their timestamps and sources.
6. Save with an identifiable name; reload it and compare legs before treating persistence as verified.

Expected result: a stored analytical strategy returned by Strategy Builder APIs. Saving does not place orders.

## Basket workflow

1. Open basket review and inspect every included leg.
2. Confirm BUY-before-SELL sequencing, product, price type and tick-rounded values.
3. Request margin if available; a margin response is not a fill guarantee.
4. Confirm Live/Sandbox and submit once.
5. Review every per-leg result, then reconcile Order Book, Trade Book and Positions.

## Portfolio workflow

Use mode, status and underlying filters; expand a card for legs/live P&L. Close uses supplied exit prices and confirmation. Delete removes the saved analytical record and is not a replacement for closing broker exposure.

## Errors and troubleshooting

Empty expiries/strikes indicate master-contract/provider input issues. Missing payoff data indicates invalid/incomplete legs. Margin or basket rejection can be provider-specific. If only some legs succeed, do not blindly resubmit the basket; reconcile existing exposure first.

## APIs and dependencies

Strategy Builder and basket/margin/history/quotes/chain endpoints; PostgreSQL saved strategies; broker mapping/master contract; analytics libraries; current mode; broker or sandbox order dispatcher. Source components are indexed in [Frontend components](../03-frontend/components-and-data-flow.md).
