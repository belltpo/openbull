# 8. Admin User Manual

The first account created through `/setup` is an administrator. This manual covers administrator-only controls plus all authenticated workflows.

## Administrator responsibilities

1. Complete initial setup and protect account credentials.
2. Configure and authenticate the broker.
3. Generate/rotate the OpenBull API key used by integrations.
4. Verify master contract and market-data health.
5. Keep global mode in sandbox until live behavior is deliberately approved.
6. Configure sandbox and futures-risk defaults/templates/maps.
7. Monitor API/error logs and service health.
8. Coordinate backup, restore tests, deployment, provider-token renewal, and incident response.

## Admin page index

| Page | Route | Admin-specific capability |
|---|---|---|
| Initial Setup | `/setup` | Creates the only supported first admin through setup |
| Broker Configuration | `/broker/config` | Saves encrypted provider configuration |
| Select Broker | `/broker/select` | Starts active provider authentication |
| API Key | `/apikey` | Views/regenerates integration key |
| Global header | all layout pages | Changes live/sandbox mode |
| Sandbox | `/sandbox` | Configures/reset/square-off/settle/wipe/reconcile actions |
| Logs | `/logs` | Global error logs and expanded API-log access |
| Futures Risk Admin | `/tools/futures-risk/admin` | Risk defaults, target templates/levels, symbol maps |

Every route and general user workflow is catalogued in the [end-user manual](../10-end-user-manual/README.md). Detailed page specifications are linked from the [page catalogue](../03-frontend/page-catalogue.md).

## Safety rules

- Confirm the top-bar mode before any order workflow.
- Test configuration changes in sandbox.
- Treat “Configured” and “Authenticated” as separate states.
- Do not expose tokens/API keys in support screenshots.
- Sandbox wipe/reset and emergency/live exits are destructive; verify mode, user, symbol, quantity, and active phase before confirming.
- Back up PostgreSQL and `.env` before migrations or deployment changes.

## 1. Initial administrator setup

Access: anonymous, only while no user exists.

1. Open `/setup` on the intended origin.
2. Enter a 3–80 character username, a syntactically valid email address, and a password of at least eight characters.
3. Confirm the password and select **Create Account**.
4. Sign in at `/login`.

Expected result: one `users` administrator row and one generated OpenBull API key. A later setup request returns 403. The application does not currently provide a web workflow for adding another user.

Screenshot: [initial setup](../assets/screenshots/setup/00-complete-page.png).

## 2. Configure a broker

Access: authenticated account.

1. Open **Broker Configuration**.
2. Select the provider.
3. Enter only fields presented for that provider. Saved secret fields intentionally remain masked/blank and may support “leave blank to keep saved value.”
4. Enter the exact redirect URI required by the page/provider. Local Dhan callback is `http://127.0.0.1:8000/dhan/callback`; production uses the deployed HTTPS origin with `/dhan/callback`.
5. Save and verify the configured state.
6. Open **Select Broker** and complete provider authentication or the provider-specific token page.
7. Wait for master-contract download/status before testing symbol-dependent pages.

Expected result: encrypted `broker_configs` plus a non-revoked, provider-valid `broker_auth` row. “Configured” alone does not mean authenticated.

Common failures:

- Callback mismatch: compare scheme, host, path, and provider portal exactly.
- Client ID/token invalid: renew through the provider-specific flow.
- Broker pages immediately return to selection: stored token failed the login resume validation.
- Symbol not found: master contract is incomplete/stale or exchange/symbol format is wrong.
- Data permission/rate limit: confirm provider subscription and wait for the documented backoff.

Screenshots: [broker selector](../assets/screenshots/broker-select/00-complete-page.png), [configuration](../assets/screenshots/broker-config/00-complete-page.png), [Dhan token](../assets/screenshots/broker-dhan-token/00-complete-page.png).

## 3. OpenBull API key

Access: authenticated owner.

1. Open `/apikey`.
2. Use **Show** only in a private environment; use **Copy** without exposing the UI when possible.
3. Put the key in the integration’s secret field, never a URL, screenshot, log, or repository.
4. Select **Generate New Key** only during a planned rotation.
5. Immediately update every REST/WebSocket/NinjaTrader client; the old key no longer authenticates.

Expected result: external clients authenticate as the owning user and use that user’s broker context. The OpenBull key is not the Dhan/Angel/Fyers/Upstox/Zerodha token.

Screenshot: [masked API-key page](../assets/screenshots/api-key/00-complete-page.png).

## 4. Global Live/Sandbox mode

Access: all authenticated users can read; only admin can mutate.

1. Inspect the header switch/banner.
2. Before changing, confirm no user/integration assumes the current mode.
3. Switch to sandbox for validation or live only after explicit approval.
4. Confirm the returned mode and refresh affected account/order pages.

Expected result: mode-sensitive calls are invalidated/refetched and external order dispatch uses the selected backend dispatcher. A mode switch does not rewrite existing live or sandbox records.

## 5. Sandbox administration

Access: authenticated page; administrative mutations require admin.

- **Reset my sandbox:** resets the documented per-user simulated state after confirmation.
- **Configuration:** capital, leverage/margin, square-off, settlement, reset, and other engine settings exposed by the current page.
- **Manual scheduler actions:** testing controls for jobs normally run at configured IST times.
- **Reconcile/wipe:** destructive operational controls; back up and verify scope first.

Workflow:

1. Ensure global mode is sandbox.
2. Record current funds, positions, orders, trades, holdings, and P&L.
3. Change one setting or invoke one action.
4. Verify the API response and corresponding persisted/account state.
5. Inspect logs for request ID and background-engine results.

Screenshots: [sandbox page](../assets/screenshots/sandbox/00-complete-page.png), [reset confirmation](../assets/screenshots/sandbox/01-reset-confirmation.png).

## 6. Futures Risk administration

Access: admin; the route also requires an active broker guard.

Manage:

- default quick-order underlying/expiry/strike method/lots/product/stop-loss/trailing behavior;
- target templates and ordered target levels;
- underlying/exchange/contract mappings used by Quick Order and NinjaTrader.

Validation procedure:

1. Open `/tools/futures-risk/admin`.
2. Change one default/template/map at a time.
3. Save and reload to verify persistence.
4. Open Quick Order and confirm the derived choices/preview match the mapping.
5. Use sandbox to place a documentation trade and verify phase/target construction.

Do not delete/rename a template or mapping without checking saved Quick Order settings and active/draft trades that reference it.

Screenshot: [Futures Risk admin](../assets/screenshots/futures-risk-admin/00-complete-page.png).

## 7. Logs and incident triage

Access: users see permitted trade/API records; error/global scopes require admin.

1. Reproduce or note the exact action time, user, mode, endpoint, symbol, and integration.
2. Open `/logs` and filter the relevant record type/time/status.
3. Copy the request/correlation ID, not credentials or full unredacted payloads.
4. Correlate with application, nginx, PostgreSQL, Redis, WebSocket, and provider state using the [logging runbook](../11-deployment-operations/logging-monitoring.md).
5. Resolve the underlying dependency/state, then run the smallest safe retry.

Typical interpretations:

- 401: session/API key invalid.
- 403: admin/broker/provider permission missing.
- 409: active phase/run or conflicting state.
- 422: field validation.
- 429/provider rate-limit message: stop repeated polling and respect backoff.
- feed stale/closed subscription: inspect broker token, adapter reconnection, and Redis/process health.

Screenshot: [logs page](../assets/screenshots/logs/00-complete-page.png).

## 8. Production operations

Application admins and host operators may be different people. The host operator must maintain systemd/nginx/TLS/PostgreSQL/Redis/backups; the application admin validates broker, mode, workflows, and users. Use the [deployment and operations manual](../11-deployment-operations/README.md) and do not represent `/health` alone as a successful production readiness test.
