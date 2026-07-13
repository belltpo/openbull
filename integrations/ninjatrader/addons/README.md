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

Enter an OpenBull API key and one exact Dhan symbol per line in this format:

```text
MCX:CRUDEOIL20JUL26FUT
NSE_INDEX:NIFTY
NFO:NIFTY28JUL26FUT
```

`CRUDEOIL_I` is a NinjaTrader-style continuous-symbol name, not a current
Dhan master-contract symbol. Use the dated MCX Dhan contract shown in the
OpenBull symbol master (currently `CRUDEOIL20JUL26FUT`), and update it when
the contract expires.

## Live chart delivery

Before clicking **Connect**, connect NinjaTrader's built-in **External Data
Feed**. Leave **Send ticks to NinjaTrader charts** selected in the AddOn.

For each symbol, set the matching NinjaTrader Instrument's **External** symbol
map to the exact Dhan symbol. For example, the AddOn input
`MCX:CRUDEOIL20JUL26FUT` requires this map:

```text
External = CRUDEOIL20JUL26FUT
```

The AddOn then sends live LTP ticks to that map and NinjaTrader builds live
second/minute bars. This does not make it a native data-vendor connection and
does not provide historical bars; use the separate historical import process
for Dhan one-minute backfill.

## Popup-free live-only candles

Click **Open Live Candles** in the AddOn window after connecting. This opens a
separate OpenBull candle window that forms one-minute OHLC candles directly
from live ticks. It starts from the first received tick, stores no history, and
does not ask NinjaTrader for historical bars, so it has no External Data Feed
historical-request popup.
