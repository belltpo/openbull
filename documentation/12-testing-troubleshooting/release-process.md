# Release Process

## Current-state warning

The repository has no checked-in CI workflow and no automated release/tag pipeline. Backend version `0.1.0`, frontend version `0.0.0`, health version, and documentation history are not currently driven from one version source.

## Required manual release procedure

1. Freeze scope and identify schema/provider/API compatibility changes.
2. Update a single proposed release version across backend/frontend/documentation or explicitly document why versions differ.
3. Run the documentation reference generator.
4. Run backend tests, frontend lint/build, sandbox E2E on disposable data, NinjaTrader checks, and the release smoke matrix.
5. Review migrations forward and restore/rollback strategy.
6. Update screenshots/manuals, integration limits, API examples, and changelog.
7. Complete independent developer and tester reviews.
8. Create PostgreSQL/environment backups.
9. Deploy to staging; validate UDS/nginx/WSS/Redis/PostgreSQL and provider sandbox/test account.
10. Tag an approved commit, deploy production, run smoke tests, and monitor logs/metrics.
11. Record deployment time, operator, commit, migration revision, backup, validation results, and incidents.

## Future CI baseline

Add jobs for Python lint/type/unit/coverage, frontend lint/type/build/unit/browser E2E, migration-from-previous-release, OpenAPI/reference drift, secret scanning, dependency/SAST scans, NinjaTrader static checks, documentation link/asset validation, and release artifact/version consistency.
