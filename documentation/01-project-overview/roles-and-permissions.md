# Roles and Permissions

## Implemented identities

| Identity | How it is established | Current capabilities |
|---|---|---|
| Anonymous visitor | No valid session cookie | Home, setup-status check, initial setup while allowed, login, broker OAuth callbacks, health endpoint |
| Authenticated user | Valid JWT cookie with live `active_sessions` JTI | Own profile, broker setup, own API key/context, own strategies/logs and non-admin feature operations subject to active broker requirements |
| Administrator | Authenticated user with `is_admin=true` | User capabilities plus global trading mode, sandbox administration, futures-risk admin mutations, analyzer toggle, global error logs, expanded API-log scope |
| External API client | Valid OpenBull API key resolving to a user and active broker context | `/api/v1/*` operations, limited by global trading mode and broker/provider permissions |
| Strategy webhook caller | Possesses a strategy-specific webhook token | Can submit the webhook action allowed by strategy state, lock, mode, and risk policy |

## Not implemented

- No `tenant` table or tenant identifier.
- No tenant membership or tenant-scoped resources.
- No `tenant_admin` role.
- No role/permission editor.
- No user-management or invitation page.
- No supported workflow for an admin to create a second user through the web UI.

The [Tenant Admin manual](../09-tenant-admin-user-manual/README.md) therefore documents a verified product gap rather than inventing permissions.

## Server-side permission matrix

| Area | Authenticated non-admin | Admin | Enforcement source |
|---|---:|---:|---|
| Read current trading mode | yes | yes | `backend/routers/trading_mode.py` |
| Change global trading mode | no | yes | `backend/routers/trading_mode.py` |
| Read sandbox summary/config/P&L | yes, scope depends on endpoint | yes | `backend/routers/sandbox.py` |
| Change sandbox config/reset/square-off/settle/wipe | no | yes | `backend/routers/sandbox.py` |
| Read own API logs | yes | yes | `backend/routers/api_logs.py` |
| Read all users' API logs/use user filter | no | yes | `backend/routers/api_logs.py` |
| Read error logs | no | yes | `backend/routers/error_logs.py` |
| Toggle analyzer mode | no | yes | `backend/api/analyzer.py` |
| Futures-risk admin configuration/templates/maps | read access varies; mutations denied | yes | `backend/routers/futures_risk.py` |
| Own saved strategies and runs | yes | yes | repository ownership filters |
| Other user's strategy/run by identifier | no; reported as not found | no unless it is owned | `backend/strategy/repository.py` |
| Live broker operation | yes when session, broker auth, mode, and provider permit | same | dependency and service validation |

UI visibility is not treated as authorization. Backend checks are the source of truth.
