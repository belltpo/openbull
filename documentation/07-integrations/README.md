# 7. Integrations

## Integration inventory

| Integration | Direction | Authentication | Current source |
|---|---|---|---|
| Angel One SmartAPI | OpenBull ↔ broker | SmartAPI key plus client code/MPIN/TOTP login | `backend/broker/angel` |
| Dhan | OpenBull ↔ broker | Partner consent flow or client ID plus access token | `backend/broker/dhan` |
| Fyers | OpenBull ↔ broker | OAuth authorization code | `backend/broker/fyers` |
| Upstox | OpenBull ↔ broker | OAuth code | `backend/broker/upstox` |
| Zerodha Kite Connect | OpenBull ↔ broker | Request-token OAuth | `backend/broker/zerodha` |
| NinjaTrader Quick Order | NinjaTrader → OpenBull | OpenBull URL and API key | `OpenBullQuickOrderIndicator.cs`, `OpenBullFuturesRiskBridge.cs` |
| NinjaTrader live-data monitor/bridge | OpenBull WebSocket → NinjaTrader | OpenBull WebSocket URL and API key | `addons/OpenBullLiveDataAddOn.cs` |
| NinjaTrader external-feed executable | OpenBull history/WS → NinjaTrader ATI/import | OpenBull API key plus local NinjaTrader client DLL | `external_feed/` |
| Bruno collection | Developer → OpenBull API | OpenBull API key/cookie as operation requires | `collections/openbull/` |
| .NET sample | Developer → OpenBull API | OpenBull API key | `sdk-dotnet/` |

Broker features are implemented through plugins, but actual availability depends on provider entitlements, subscriptions, segments, API versions, and token state.

- [Broker integrations](brokers.md)
- [Dhan setup and data flow](dhan.md)
- [NinjaTrader integration](ninjatrader.md)
