# OpenBull Live Data AddOn

`OpenBullLiveDataAddOn.cs` is an independent NinjaTrader 8 AddOn. It does not
reference, configure, or modify OpenBull Quick Order, indicators, strategies,
charts, accounts, or order routing.

It adds **New > OpenBull Live Data** in the NinjaTrader Control Center. Its
window connects to OpenBull's local WebSocket proxy and displays live quote
updates in a grid.

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

The AddOn displays values only. It does not create NinjaTrader chart bars or a
native NinjaTrader data-vendor connection.
