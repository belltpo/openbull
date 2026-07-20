# NinjaTrader Integration

## Components and installation category

| File | NinjaTrader category/purpose |
|---|---|
| `OpenBullQuickOrderIndicator.cs` | Indicator. Per-chart Quick Order UI; polls OpenBull preview/trade endpoints. |
| `OpenBullFuturesRiskBridge.cs` | AddOn. Relays/coordinates futures-risk drawing and application actions independent of live-data provider behavior. |
| `Bell_LongEntryTool.cs`, `Bell_ShortEntryTool.cs` | Drawing tools used by the futures-risk/Quick Order workflow. |
| `addons/OpenBullLiveDataAddOn.cs` | Control Center AddOn under New → OpenBull Live Data; monitors WebSocket quotes and can forward live ticks to NinjaTrader's built-in External Data Feed through ATI. |
| `external_feed/OpenBullExternalDataFeedBridge.cs` | Standalone executable using `NinjaTrader.Client.dll` to push live last prices and export history files. |

Quick Order and live-data add-on are separate. The live-data add-on must not modify or replace the Quick Order indicator.

## Quick Order configuration

- OpenBull URL: base URL only, for example local `http://127.0.0.1:8000` or the deployment HTTPS base URL.
- API Key: OpenBull-generated API key.
- Live Poll Ms: constrained by the indicator to 500–10,000 ms; default 1,000 ms. This polls `/api/v1/futures-risk/quick-order/preview` and is not the Dhan WebSocket interval.
- Underlying/exchange/expiry/strike method/CE/PE/lots/SL/template/product: translated into Quick Order option/settings/trade requests.

The indicator can be applied separately to multiple charts. Each instance retains its chart settings and polls OpenBull; server-side phase rules and broker rate limits still apply globally per underlying/user.

## Live-data AddOn workflow

1. Compile/import the AddOn into NinjaTrader 8 and restart NinjaTrader.
2. Open Control Center → New → OpenBull Live Data.
3. Enter the OpenBull WebSocket URL and OpenBull API key.
4. Enter one exact `EXCHANGE:SYMBOL` per line.
5. Connect and verify authenticated status plus updating rows.
6. To send ticks into charts, enable NinjaTrader's built-in External Data Feed/ATI and select “Send ticks to NinjaTrader charts”.
7. Create/edit a NinjaTrader instrument with an exact External symbol map matching the instrument name sent through ATI.

The AddOn is not a native NinjaTrader market-data vendor adapter. The supported bridge relies on the built-in External Data Feed/ATI. It supplies live ticks only; historical bars require an import workflow.

## Historical data

The standalone bridge can request OpenBull `/history`, write NinjaTrader `.Last.txt` files, and leave final import to Tools → Historical Data. Direct writes into NinjaTrader's private historical database are not implemented.

## Runtime validation matrix

Before release, record:

- NinjaTrader exact version and compatible `NinjaTrader.Client.dll` version.
- Successful NinjaScript compile without duplicate files/classes.
- AddOn menu entry appears once and closes without UI-thread errors.
- ATI enabled and port 36973 reachable when chart injection is used.
- External Data Feed connected and exact symbol maps configured.
- LTP updates for NSE/NFO/MCX examples during relevant market hours.
- Two or more charts/Quick Order instances retain independent symbols/settings.
- Hosted HTTPS/WSS, API-key rotation, disconnect/reconnect, and provider-token expiry behavior.

Do not assume workspace/template storage masks API keys; verify the NinjaTrader version's serialization behavior and use a restricted documentation key for screenshots.
