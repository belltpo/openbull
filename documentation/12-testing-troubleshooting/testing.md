# Testing Procedures

## Backend unit suite

```powershell
cd D:\openbull
.\.venv\Scripts\python.exe -m unittest discover -s backend\test -p "test_*.py" -v
```

At the initial documentation audit, 29 tests passed. Record the commit and new count in each release; do not treat this historical count as a permanent expectation.

Coverage includes selected WebSocket auth/subscription/modes, Dhan subscription deduplication, Redis/symbol caches, strike selection, futures-risk multi-symbol/quotes/sandbox behavior, scheduler, and sandbox quote context. Tests that contact live providers must be separately marked and require restricted test credentials.

## Sandbox E2E

`sandbox_e2e_test.py` exercises persisted sandbox workflows and mutates the configured sandbox database. Run only against a disposable test database/account:

```powershell
.\.venv\Scripts\python.exe .\sandbox_e2e_test.py
```

## Frontend

```powershell
cd D:\openbull\frontend
npm run lint
npm run build
```

There are no current frontend unit or browser-E2E commands. Manual workflow/screenshot validation is required until those suites are added.

At the 2026-07-20 baseline, the production build passed. ESLint failed with 42 errors and 12 warnings, primarily React hook/compiler/ref rules; this is a release-quality gap even though TypeScript/Vite can build. The exact lint output is source-dependent and must be rerun rather than copied forward as a permanent count.

## NinjaTrader static checks

```powershell
powershell -ExecutionPolicy Bypass -File .\integrations\ninjatrader\test-integration-isolation.ps1
powershell -ExecutionPolicy Bypass -File .\integrations\ninjatrader\test-quick-order-symbol-mapping.ps1
```

The external-feed executable build/test additionally requires the matching NinjaTrader installation and `NinjaTrader.Client.dll`; it can write artifacts or feed data and must be run on a designated workstation.

## Required release smoke tests

1. Setup/login/logout/session expiry.
2. Broker configure/login/token expiry/master contract.
3. One REST quote plus WebSocket LTP/quote/depth where supported.
4. Global sandbox/live permission behavior.
5. Sandbox market/limit/SL fill, position, funds, P&L, close, restart catch-up.
6. Order/trade/position/holding pages.
7. Analytics route load and expected validation/error states.
8. Strategy save/load/run/webhook/stop/close/ownership tests.
9. Futures-risk draft/place/targets/partial/emergency/history and multi-symbol cards.
10. NinjaTrader compile, multi-chart Quick Order isolation, hosted API, disconnect/reconnect.
11. Production UDS, nginx, WSS, Redis, PostgreSQL, logs, backup and restore drill.

## Documentation gate

```powershell
cd D:\openbull
.\.venv\Scripts\python.exe .\documentation\tools\validate_documentation.py
```

This rejects stale generated references, broken local links, missing/redirected/blank route captures, captured failed-load states, missing important-action evidence/annotations, incomplete manual chapter categories, unrecorded screenshots, and obvious credential literals in Markdown. It complements review; it does not prove provider entitlements, current prices, successful live orders, or production infrastructure.
