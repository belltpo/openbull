# Documentation Change Log

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

The repository has no Git release tags at this baseline. `backend.main` exposes application version `0.1.0`, while `frontend/package.json` uses package version `0.0.0`; neither is treated here as a published product release. Until maintainers introduce signed/tagged releases, Git commit IDs and dates are the only verifiable version identifiers. See [Version baseline](version-baseline.md).
