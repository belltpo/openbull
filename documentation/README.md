# OpenBull Documentation

This directory is the maintained documentation set for the OpenBull source tree at the repository root. It is intentionally separate from the legacy `docs/` directory so that developers, testers, operators, support staff, administrators, and users have one navigable source of truth.

## Documentation map

1. [Project Overview](01-project-overview/README.md)
2. [System Architecture](02-system-architecture/README.md)
3. [Frontend Documentation](03-frontend/README.md)
4. [Backend Documentation](04-backend/README.md)
5. [Database Documentation](05-database/README.md)
6. [API and WebSocket Documentation](06-api-websocket/README.md)
7. [Integrations](07-integrations/README.md)
8. [Admin User Manual](08-admin-user-manual/README.md)
9. [Tenant Admin User Manual](09-tenant-admin-user-manual/README.md)
10. [End-User Manual](10-end-user-manual/README.md)
11. [Deployment and Operations](11-deployment-operations/README.md)
12. [Testing and Troubleshooting](12-testing-troubleshooting/README.md)
13. [Change Log and Version History](13-change-log/README.md)

Supporting material:

- [Generated inventories](inventories/README.md)
- [Screenshot catalogue](assets/screenshots/README.md)
- [Reusable documentation templates](templates/README.md)
- [Validation and review records](validation/README.md)
- [Documentation maintenance guide](CONTRIBUTING.md)

## Source-of-truth policy

Documentation statements must be traceable to one or more of the following:

1. Current application source under `backend/`, `frontend/src/`, `integrations/`, `install/`, and root configuration files.
2. Generated OpenAPI and SQLAlchemy metadata inventories.
3. A recorded runtime validation against a named Git commit and environment.
4. An official external-provider document linked from the relevant integration guide.

Secrets, access tokens, API keys, passwords, private URLs, and personally identifying account values must never be copied into this directory. Screenshots must use redacted or documentation-only credentials.

## Version covered

The baseline is recorded in [documentation/13-change-log/version-baseline.md](13-change-log/version-baseline.md). Run the reference generator after route, model, or configuration changes:

```powershell
cd D:\openbull
.\.venv\Scripts\python.exe .\documentation\tools\generate_reference.py
```

Then complete the checklist in [CONTRIBUTING.md](CONTRIBUTING.md) before merging a release.

Validate the full set, including generated references, internal links, route coverage, screenshot redirects/files, and obvious Markdown credential literals:

```powershell
.\.venv\Scripts\python.exe .\documentation\tools\validate_documentation.py
```

The current screenshot baseline contains 40 verified route states and 17 numbered safe action states. See the [rendered screenshot catalogue](assets/screenshots/README.md), [numbered annotations](assets/screenshots/annotations.md), and [runtime manifest](assets/screenshots/manifest.json). The populated records are labelled sandbox-only fixtures; provider-dependent prices, live-order outcomes, and production infrastructure remain environment-specific evidence requirements listed under [known limitations](validation/known-limitations.md).
