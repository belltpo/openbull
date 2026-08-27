# Documentation Change Log

## 2026-08-27 — OpenBull 1.0.0

- Established `1.0.0` as the first tagged OpenBull product release.
- Aligned backend, frontend, FastAPI, health, and generated OpenAPI version metadata.
- Recorded the manual release and validation procedure for future releases.
- Release validation: 46 backend unit tests, documentation validation, NinjaTrader
  isolation/mapping checks, and the frontend production build passed. Frontend
  lint retains the documented pre-existing baseline of 42 errors and 12 warnings.

## 2026-07-22 — Futures-Risk live exit safety

- Documented persistent single-flight exit state, broker-position reconciliation, and the one-failure circuit breaker.
- Added operator guidance for direct broker-terminal closes and the **Verify broker & resume** control.
- Added the reconciliation/recovery endpoints and broker-position snapshot cache to the maintained inventories.

## 2026-07-20 — Initial source-backed documentation baseline

- Created separate maintained `documentation/` tree.
- Added source-generated API, route, database, environment, OpenAPI, and commit inventories.
- Added architecture, frontend, backend, database, API/WebSocket, integration, role, deployment, operations, testing, troubleshooting, release, and maintenance guides.
- Recorded tenant-admin as not implemented rather than assuming tenancy.
- Recorded current operational/security/test gaps for review.
- Added the first route-level page catalogue and audience-specific manuals; remaining provider/device evidence is tracked explicitly rather than represented as complete.
- Captured 40 route states and 7 safe action states in an isolated documentation database/browser profile.
- Added deterministic reference generation and documentation validation gates.
- Recorded verification results: 29 backend tests passed, frontend build passed with chunk warnings, NinjaTrader isolation/mapping checks passed, and frontend lint remains at 42 errors/12 warnings.
- Recorded provider/live-market and production-host states as external validation requirements rather than inventing evidence.

## Product version history status

The July documentation baseline predates tagged releases and remains recorded in
[Version baseline](version-baseline.md). OpenBull `1.0.0` is the first product
release to align backend, frontend, health, and OpenAPI version metadata.
