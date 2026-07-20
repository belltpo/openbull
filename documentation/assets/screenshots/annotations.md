# Numbered Screenshot Annotations

The PNG files are unmodified runtime evidence. Numbering is encoded in each filename (`00`, `01`, `02`) so screenshots remain faithful to the rendered application. The callouts below are the maintained annotations; no arrow or label is painted over a control that the application did not render.

| No. | Page | Evidence | Action/control | Expected visible result |
|---:|---|---|---|---|
| 1 | Broker Configuration | [01](broker-config/01-open-broker-selector.png) | Select the Broker combobox. | The supported broker list opens; no credential is submitted. |
| 2 | API Playground | [01](playground/01-websocket-mode.png) | Select **WebSocket**. | Connection controls, message composer, templates, and message log replace REST controls. |
| 3 | Order Book | [01](order-book/01-modify-order.png) | Select **Modify** on the documentation order. | Quantity, price type, price, and trigger fields open; no update is submitted. |
| 4 | Order Book | [02](order-book/02-cancel-order-confirmation.png) | Select **Cancel** on the documentation order. | A single-order confirmation opens; cancellation is not confirmed. |
| 5 | Order Book | [03](order-book/03-cancel-all-confirmation.png) | Select **Cancel All**. | A cancel-all confirmation opens; no order is changed. |
| 6 | Positions | [01](positions/01-close-position-confirmation.png) | Select **Close** on the documentation position. | The reverse-side market close and remaining quantity are shown; it is not submitted. |
| 7 | Positions | [02](positions/02-close-all-confirmation.png) | Select **Close All**. | A portfolio-wide close confirmation opens; no position is changed. |
| 8 | Sandbox | [01](sandbox/01-reset-confirmation.png) | Select **Reset my sandbox**. | A destructive-action confirmation appears; the capture does not confirm it. |
| 9 | Strategy Portfolio | [01](strategy-portfolio/01-expanded-strategy.png) | Expand the documentation strategy. | Both sandbox legs, strikes, quantities, prices, and states become visible. |
| 10 | Strategy Portfolio | [02](strategy-portfolio/02-close-strategy.png) | Select **Close strategy**. | The exit-price workflow opens; it is not submitted. |
| 11 | Strategy Portfolio | [03](strategy-portfolio/03-delete-strategy-confirmation.png) | Select **Delete**. | A destructive confirmation opens; the strategy remains intact. |
| 12 | Futures Risk | [01](futures-risk/01-phase-history.png) | Select **Phase history**. | Historical filters and source-defined demonstration phase cards are shown. |
| 13 | Futures Risk | [02](futures-risk/02-quick-order.png) | Select **Quick Order**. | The quick-order dialog opens without placing an order. |
| 14 | Futures Risk card demonstration | [01](futures-risk-card-demo/01-expand-all.png) | Select **Expand all**. | Every instrument timeline expands using the page's source-defined demo records. |
| 15 | Strategy Wizard | [01](strategy-wizard/01-signal-driven.png) | Select **Signal-driven**. | Direction and per-leg signal fields replace batch-only inputs. |
| 16 | Strategy Detail | [01](strategy-detail/01-setup-tab.png) | Select **Setup** on the documentation strategy. | Persisted universe, execution, risk, schedule, and leg settings are displayed. |
| 17 | Strategy Detail | [02](strategy-detail/02-webhook-tab.png) | Select **Webhook**. | The redacted webhook URL, alert payload, and token-rotation control are displayed. |

Provider login, live order submission, market ticks, broker rejection, NinjaTrader compilation, and production recovery are deliberately not simulated. Their evidence requirements are listed in [Known limitations and external validation](../../validation/known-limitations.md).
