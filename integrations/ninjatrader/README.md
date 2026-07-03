# OpenBull NinjaTrader Quick Order Indicator

`OpenBullQuickOrderIndicator.cs` is a standalone NinjaTrader 8 indicator that
adds a compact chart overlay for sending Futures-Risk quick orders to OpenBull.

## Flow

`NinjaTrader button -> OpenBull API key endpoint -> Futures-Risk quick-order service -> broker`

The indicator does not place broker orders directly. OpenBull remains the source
of truth for phase numbering, option order placement, futures-based stop-loss,
targets, trailing behavior, sandbox/live mode, and rejected-order handling.

## OpenBull Endpoint

The indicator posts to:

```text
POST /api/v1/futures-risk/quick-order
```

It also uses these API-key endpoints for live preview and settings sync:

```text
POST /api/v1/futures-risk/quick-order/preview
POST /api/v1/futures-risk/quick-order/options
POST /api/v1/futures-risk/quick-order/settings
POST /api/v1/futures-risk/quick-order/settings/delete
```

Required auth:

```text
apikey in JSON body
```

or:

```text
X-API-KEY header
```

## NinjaTrader Setup

1. In OpenBull, create/copy your API key from the API key page.
2. Keep OpenBull backend running, normally at `http://127.0.0.1:8000`.
3. In NinjaTrader 8, open `New > NinjaScript Editor`.
4. Right-click `Indicators`, choose `New Indicator`, then replace the generated
   content with `OpenBullQuickOrderIndicator.cs`.
5. Compile.
6. Restart the OpenBull backend after pulling this integration, otherwise NT
   will receive `{"detail":"Not Found"}` for the new API routes.
7. Add `OpenBull Quick Order` to any chart.
8. Set:
   - `OpenBull URL`
   - `API Key`
   - `Underlying`
   - `Expiry`
   - `CE Strike`
   - `PE Strike`
   - `Lots`
   - `SL Points`
   - `Target Template Id`

Use `Target Template Id = 0` only when using override targets. Otherwise set it
to the OpenBull target template id you want this chart to use.

## Chart Widget Behavior

- `S` opens a separate quick settings card beside the order buttons.
- `X` collapses the quick-order popup into a small `OB` restore button.
- Click `OB` to show the quick-order popup again; you do not need to remove and
  add the indicator.
- Drag the top handle/header or the minimized `OB` button to move the widget
  anywhere on the chart.
- The settings card uses editable dropdowns for instrument, expiry, CE strike,
  PE strike, target template id, and product. If OpenBull cannot return a list
  yet, the current value is still editable manually.
- `Refresh` reloads dropdown values from OpenBull.
- `Save` creates or updates the selected contract quick-order setup in
  OpenBull's per-contract settings store.
- `Delete` removes the selected contract quick-order setup from OpenBull.
- While the settings card is open, dropdown/default values are refreshed from
  OpenBull about every 10 seconds.
- Futures, CE, and PE LTP values are polled from OpenBull every five seconds via
  `/api/v1/futures-risk/quick-order/preview`.
- After a successful quick order, the indicator fetches the created Futures-Risk
  trade and creates/updates a tagged `Bell_LongEntryTool` or
  `Bell_ShortEntryTool` on the chart.
- The last linked OpenBull trade id is stored with the indicator. When the chart
  or workspace reloads, the indicator fetches that trade from OpenBull and
  restores the same tagged Bell drawing tool instead of losing the levels.
- If you manually delete the linked Bell drawing tool from the chart, the
  indicator respects that deletion and does not recreate it until a new quick
  order links a new trade.
- The entry line is fixed after order placement. Stop-loss and pending target
  lines can be dragged vertically; on mouse release the Bell drawing tool syncs
  the updated futures prices to OpenBull through
  `PUT /api/v1/futures-risk/trades/{trade_id}/levels`.
- The entry label shows `L React` / `S React` with the current linked-trade MTM.
  MTM and target status refresh through OpenBull polling. OpenBull remains the
  execution source of truth; broker-side target/SL orders are not placed in
  advance by this indicator.

## Button Mapping

- `Buy CE` sends `option_type=CE`, `side=BUY`
- `Sell CE` sends `option_type=CE`, `side=SELL`
- `Buy PE` sends `option_type=PE`, `side=BUY`
- `Sell PE` sends `option_type=PE`, `side=SELL`

Bullish Futures-Risk direction creates `Bell_LongEntryTool`; bearish direction
creates `Bell_ShortEntryTool`.

## Advanced Level Management

The indicator now uses the Bell drawing tools as its chart-level manager:

1. Click a quick-order button.
2. OpenBull places/records the Futures-Risk trade.
3. NT loads that trade id and creates a tagged Bell long/short drawing tool.
4. Drag SL or a pending target line on the Bell tool.
5. Release the mouse; OpenBull immediately receives the new level plan.
6. OpenBull refresh updates the same tagged Bell tool with MTM and target
   status, so completed targets become visible but locked.

Use a chart with a price scale matching the selected underlying futures contract
for accurate level placement. If the chart instrument has a completely different
price scale, the OpenBull futures levels may render outside the visible panel.

The copied Bell drawing tools still support manual linking through
`OpenBull Trade ID`; quick orders now auto-create and auto-link those same
tools using tag `OpenBull_FR_<trade_id>`.
