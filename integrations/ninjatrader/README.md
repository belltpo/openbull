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
- Futures, CE, and PE LTP values are polled from OpenBull every two seconds via
  `/api/v1/futures-risk/quick-order/preview`.

## Button Mapping

- `Buy CE` sends `option_type=CE`, `side=BUY`
- `Sell CE` sends `option_type=CE`, `side=SELL`
- `Buy PE` sends `option_type=PE`, `side=BUY`
- `Sell PE` sends `option_type=PE`, `side=SELL`

The first version is intentionally independent from `Bell_LongEntryTool.cs` and
`Bell_ShortEntryTool.cs`. Those drawing tools can be integrated later as a level
provider after the API path is proven stable.
