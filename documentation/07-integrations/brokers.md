# Broker Integrations

## Plugin contract

Each broker folder supplies provider-specific auth, data, funds, margin, orders, master-contract download/mapping, and streaming adapter modules. `plugin.json` provides the displayed name, OAuth type, auth URL template, and declared exchange list. Common OpenBull services dynamically load the active provider implementation.

## Current plugin matrix

| Broker | Login flow in current UI/API | Callback/internal route | Declared exchanges |
|---|---|---|---|
| Angel One | Save SmartAPI key; internal client-code/MPIN/TOTP form | `POST /angel/login` | NSE, BSE, NFO, BFO, CDS, MCX and declared index variants |
| Dhan | Partner consent after saving App ID/secret/client ID/redirect, or manual access token | `/dhan/callback`; `POST /auth/dhan/token-login` | NSE, BSE, NFO, BFO, CDS, BCD, MCX and declared index variants |
| Fyers | OAuth authorization code | `/fyers/callback` | NSE, BSE, NFO, BFO, CDS, MCX and declared index variants |
| Upstox | OAuth code | `/upstox/callback` | NSE, BSE, NFO, BFO, CDS, BCD, MCX, index/global variants declared by plugin |
| Zerodha | Kite request token | `/zerodha/callback` | NSE, BSE, NFO, BFO, CDS, MCX, NCO and declared index/global variants |

The exchange list is plugin metadata, not proof that an account has the segment enabled.

## Generic setup workflow

1. Create/configure the provider application in the broker developer portal.
2. Set the exact callback shown below for the deployment base URL.
3. In OpenBull, open Broker Configuration, select the broker, and save the fields displayed for that broker.
4. Open Select Broker and complete the provider login or internal credential form.
5. Wait for master-contract download status to report success.
6. Verify funds/account data, one REST quote, WebSocket authentication, and one subscribed symbol before enabling live orders.
7. Test order workflows in global sandbox mode first.

### Callback patterns

| Broker | Callback pattern |
|---|---|
| Upstox | `<PUBLIC_BASE_URL>/upstox/callback` |
| Zerodha | `<PUBLIC_BASE_URL>/zerodha/callback` |
| Fyers | `<PUBLIC_BASE_URL>/fyers/callback` |
| Dhan | `<PUBLIC_BASE_URL>/dhan/callback` |
| Angel One | No OAuth callback in the current flow |

Use the actual HTTPS domain in production and the same local hostname consistently during development. The provider's configured callback must match exactly.

## Renewal and failure handling

- A saved API/app key does not guarantee a current broker access token.
- Expired/revoked broker sessions require provider login again.
- Market-data APIs may require a paid/activated data subscription separate from order APIs.
- Provider rate limits, symbol formats, market sessions, and connection limits are external constraints; link official provider documentation in release-specific support notes.
- Successful broker re-login triggers master-contract refresh and broker-context cache invalidation; verify the current stream actually replaced its credentials.
