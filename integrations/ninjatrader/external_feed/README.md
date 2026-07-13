# OpenBull External Data Feed bridge

This is a standalone console bridge. It uses NinjaTrader's built-in **External
Data Feed** and `NinjaTrader.Client.dll`; it does not modify or use OpenBull
Quick Order, indicators, strategies, or AddOns.

It has two supported data paths:

| Need | Bridge action | NinjaTrader action |
| --- | --- | --- |
| Live / second / minute bars | Sends every OpenBull Dhan LTP tick through `Client.Last()` | Connect the built-in External Data Feed; NinjaTrader builds the live bars |
| 1-minute history | Fetches Dhan intraday one-minute OHLCV through OpenBull and writes a NinjaTrader import file | Import the generated `*.Last.txt` file once |

NinjaTrader's External Data Feed DLL functions are real-time functions. Its
historical importer is the supported way to backfill Dhan one-minute candles.

## One-time NinjaTrader setup

1. Enable NinjaTrader's ATI/DLL listener. With NinjaTrader closed, you can run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\enable-ati.ps1
   ```

   Or enable it manually in **Tools > Options > Automated Trading Interface**.
2. In **Tools > Instruments**, create `CRUDEOIL20JUL26FUT` as an MCX futures
   instrument with tick size `1`.
3. In that instrument's **Symbol Map**, set the **External** mapping to exactly
   `CRUDEOIL20JUL26FUT`.
4. In **Connections**, connect **External Data Feed**.

The instrument name and its External mapping must match `--nt-instrument`.

## Build

```powershell
cd D:\openbull\integrations\ninjatrader\external_feed
powershell -ExecutionPolicy Bypass -File .\build-external-feed.ps1
```

Run the offline converter test with:

```powershell
powershell -ExecutionPolicy Bypass -File .\test-external-feed.ps1
```

## Export and import 1-minute Dhan candles

OpenBull must be running, and the selected OpenBull API key must have a saved
Dhan login. Run this once for the desired date range:

```powershell
.\bin\OpenBullExternalDataFeedBridge.exe `
  --api-key "YOUR_OPENBULL_API_KEY" `
  --nt-instrument "CRUDEOIL20JUL26FUT" `
  --symbol "CRUDEOIL20JUL26FUT" `
  --exchange "MCX" `
  --from "2026-07-10" --to "2026-07-13" --export-only
```

The output defaults to:

```text
%USERPROFILE%\Documents\NinjaTrader 8\import\CRUDEOIL20JUL26FUT.Last.txt
```

In NinjaTrader open **Tools > Historical Data > Import**, select:

- Format: **NinjaTrader (end of bar timestamps)**
- Data type: **Last**
- Time zone: **India Standard Time**

Then choose the generated `.Last.txt` file. NinjaTrader can build 5-minute,
15-minute, and other minute charts from this imported one-minute history.

## Start live data

Keep **External Data Feed** connected, then run the bridge without
`--export-only`:

```powershell
.\bin\OpenBullExternalDataFeedBridge.exe `
  --api-key "YOUR_OPENBULL_API_KEY" `
  --nt-instrument "CRUDEOIL20JUL26FUT" `
  --symbol "CRUDEOIL20JUL26FUT" `
  --exchange "MCX" `
  --skip-history
```

Use Ctrl+C to stop it. The bridge prints a clear message when NinjaTrader is
not accepting ticks; in that case confirm ATI, External Data Feed, and the
External symbol map.

## Contract rollover

`CRUDEOIL_I` is not a Dhan master-contract symbol. Use the current dated Dhan
contract and create the matching NinjaTrader instrument/mapping. Update all
three values at expiry: `--nt-instrument`, `--symbol`, and the External symbol
map.
