# OpenBull NinjaTrader Quick Order Indicator

`OpenBullQuickOrderIndicator.cs` is a NinjaTrader 8 indicator that adds a
compact chart overlay for Futures-Risk quick orders and live market data from
OpenBull. `addons/OpenBullLiveDataClient.cs` is its shared WebSocket transport.

`provider/OpenBullDataProvider.cs` is a native NinjaTrader **data-provider**
adapter. It appears in NinjaTrader's Connections menu as `OpenBull`, rather
than only being available to this indicator.

## Flow

`Dhan WebSocket -> OpenBull stream proxy -> NinjaTrader indicator`

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

For live ticks the indicator connects to:

```text
ws://127.0.0.1:8765
```

It authenticates with the same OpenBull API key and subscribes to the resolved
futures, CE, PE, and active-position option contracts. OpenBull pools duplicate
symbols across charts before sending subscriptions upstream to Dhan.

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
4. Copy `OpenBullQuickOrderIndicator.cs` into NinjaTrader's
   `bin/Custom/Indicators` folder and `addons/OpenBullLiveDataClient.cs` into
   `bin/Custom/AddOns`.
5. Compile. NinjaTrader must be allowed to use `System.Net.WebSockets`.
6. Restart the OpenBull backend after pulling this integration, otherwise NT
   will receive `{"detail":"Not Found"}` for the new API routes.
7. Add `OpenBull Quick Order` to any chart.
8. Set:
   - `OpenBull URL`
   - `API Key`
   - `Use Live WebSocket = true`
   - `Live WebSocket URL = ws://127.0.0.1:8765`
   - `Underlying`
   - `Expiry`
   - `CE Strike`
   - `PE Strike`

## Native OpenBull connection

The native connection is data-only: it supplies realtime ticks to NinjaTrader
but never places a Dhan order. OpenBull remains the order-routing boundary.

Build and install the provider from a PowerShell prompt:

```powershell
cd D:\openbull
powershell -ExecutionPolicy Bypass -File .\integrations\ninjatrader\provider\build-native-provider.ps1
```

Restart NinjaTrader, then open `Connections > Configure` and create/select
`OpenBull`. Set the OpenBull API key in the **Password** field and keep the
local WebSocket URL as `ws://127.0.0.1:8765`.

For contracts whose NinjaTrader name does not exactly match Dhan's symbol,
set **Symbol mappings** using this format:

```text
NIFTY 07-26=NFO:NIFTY28JUL26FUT; CRUDEOIL 08-26=MCX:CRUDEOIL18MAY26FUT
```

The current provider supplies realtime data. Historical bars remain the
responsibility of the connection already used for chart history.
   - `Lots`
   - `Product` defaults to `MIS` and can be changed/saved per contract
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
- Futures, CE, and PE LTP values stream from OpenBull over WebSocket. REST
  preview runs every five seconds only to resolve contracts and refresh the
  aggregate MTM fallback. It uses OpenBull's cache and does not repeatedly hit
  Dhan when the stream is healthy.
- The widget shows a reconnecting/error status when the stream is unavailable;
  it does not treat stale prices as fresh data.
- After a successful quick order, the indicator fetches the created Futures-Risk
  trade and creates/updates a tagged `Bell_LongEntryTool` or
  `Bell_ShortEntryTool` on the chart.
- The indicator restores one tagged Bell drawing tool per current-session
  OpenBull phase/trade for the selected instrument. When the chart or workspace
  reloads, it fetches those phases from OpenBull and restores their levels
  instead of losing them.
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

## Supported live symbols

The stream accepts all symbols present in OpenBull's Dhan master-contract cache
for Dhan-supported exchanges, including `NSE`, `NSE_INDEX`, `NFO`, and `MCX`.
Examples:

```text
NSE       RELIANCE
NSE_INDEX NIFTY
NFO       NIFTY28JUL26FUT
NFO       BANKNIFTY28JUL2655900CE
MCX       CRUDEOIL18MAY26FUT
```

Live data remains subject to the Dhan account's market-data permissions and
subscription capacity. The integration is a NinjaTrader indicator feed; it
does not register Dhan as a native NinjaTrader brokerage/data-provider, so it
does not create NinjaTrader chart bars by itself.
