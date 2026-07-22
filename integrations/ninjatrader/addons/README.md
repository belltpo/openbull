# OpenBull Live Data AddOn

`OpenBullLiveDataAddOn.cs` is an independent NinjaTrader 8 AddOn. It does not
reference, configure, or modify OpenBull Quick Order, indicators, strategies,
accounts, or order routing.

It adds **New > OpenBull Live Data** in the NinjaTrader Control Center. Its
window connects to OpenBull's local WebSocket proxy and displays live quote
updates in a grid. It can also send those ticks to NinjaTrader's built-in
External Data Feed so that mapped charts build live bars without a separate
PowerShell bridge process.

## Install

1. Close NinjaTrader.
2. Copy `OpenBullLiveDataAddOn.cs` to:

   ```text
   C:\Users\<Windows-user>\Documents\NinjaTrader 8\bin\Custom\AddOns\
   ```

3. Start NinjaTrader and compile with **F5** in the NinjaScript Editor.
4. Open **New > OpenBull Live Data**.

## Connect

Start OpenBull first. The normal local WebSocket URL is:

```text
ws://127.0.0.1:8765
```

Enter an OpenBull API key and one exact broker symbol per line. When chart
delivery is enabled, map it to NinjaTrader's exact full chart instrument with
`=>`:

```text
MCX:CRUDEOIL19AUG26FUT => CRUDEOIL19AUG26FUT AUG26
```

The left side is sent to OpenBull/Dhan. The right side is passed to
`NinjaTrader.Client.Last()` and must match the chart's `@INSTRUMENT_FULL`
value exactly. A mapping is mandatory when **Send ticks to NinjaTrader
charts** is selected; the AddOn refuses to forward an unresolved symbol so
NinjaTrader cannot silently auto-create a Stock with the futures name.

`CRUDEOIL_I` is a NinjaTrader-style continuous-symbol name, not a current
Dhan master-contract symbol. Use the dated MCX Dhan contract shown in the
OpenBull symbol master (currently `CRUDEOIL20JUL26FUT`), and update it when
the contract expires.

## Live chart delivery

Before clicking **Connect**, connect NinjaTrader's built-in **External Data
Feed**. Leave **Send ticks to NinjaTrader charts** selected in the AddOn.

The AddOn validates the right-hand NinjaTrader instrument before opening the
WebSocket and then sends live LTP ticks to that exact contract. NinjaTrader
builds live second/minute bars. This does not make it a native data-vendor
connection and does not provide historical bars; use the separate historical
import process for Dhan one-minute backfill.

## Popup-free live-only candles

Click **Open Live Candles** in the AddOn window after connecting. This opens a
separate OpenBull candle window that forms one-minute OHLC candles directly
from live ticks. It starts from the first received tick, stores no history, and
does not ask NinjaTrader for historical bars, so it has no External Data Feed
historical-request popup.
