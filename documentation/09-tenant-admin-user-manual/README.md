# 9. Tenant Admin User Manual

## Current implementation status

OpenBull does **not** currently implement tenants or a tenant-administrator role.

The source contains:

- A `users` table with an `is_admin` boolean.
- Per-user ownership for credentials, API keys, strategies, runs, and logs.
- Initial setup that allows one admin account.

The source does not contain:

- A tenant table or tenant ID on resources.
- Tenant membership/invitation/provisioning.
- A tenant-admin permission or scope.
- Tenant billing, branding, policy, data partition, or administration pages.

Therefore no tenant-admin access or workflow is documented as available. Calling ordinary per-user ownership “tenancy” would be misleading.

## Requirements before this manual can become operational

1. Define tenant, membership, role, ownership, and lifecycle models.
2. Add migration/backfill and hard database/query scoping.
3. Add server-side permission dependencies and negative cross-tenant tests.
4. Add tenant-admin account/user/policy pages.
5. Add audit events, invitations, suspension, data export/deletion, and recovery procedures.
6. Add tenant-aware broker credentials, API keys, strategies, logs, and background-job isolation.
7. Run a security review before enabling multiple independent organizations.

Until then, deploy separate OpenBull instances when separate administrative/security boundaries are required.
