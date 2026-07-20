# Configuration and Environment Variables

The generated [environment inventory](../inventories/environment-variables.md) is sourced from `backend.config.Settings`. `.env.example` is a template, not a complete production hardening guide.

## Required secrets

| Variable | Purpose | Rotation impact |
|---|---|---|
| `APP_SECRET_KEY` | JWT signing/security secret | Existing browser sessions become invalid |
| `ENCRYPTION_PEPPER` | Password/API-key derivation and encrypted-secret material | Changing without a migration can prevent verification/decryption of existing data |
| `DATABASE_URL` password | PostgreSQL authentication | Update server and application atomically |

Generate high-entropy unique values and restrict `.env` permissions.

## Production-critical settings

| Variable | Production guidance |
|---|---|
| `FRONTEND_URL` | Exact public HTTPS base URL |
| `CORS_ORIGINS` | Explicit trusted origins only |
| `COOKIE_SECURE` | `true` behind HTTPS |
| `WEBSOCKET_URL` | Public `wss://<domain>/ws/` URL returned to clients |
| `WEBSOCKET_HOST/PORT` | Internal listener, normally 127.0.0.1:8765 |
| `REDIS_URL` | Reachable Redis URI; protect remote Redis with network/auth/TLS controls |
| `LOG_*`, `API_LOG_DB_MAX_ROWS`, `ERROR_LOG_DB_MAX_ROWS` | Size/retention appropriate to disk and audit policy |
| Rate limits | Tune only after measured traffic and broker constraints |

`VALID_BROKERS` exists in Settings but current plugin loading scans installed `plugin.json` files; do not treat this variable as a security allow-list without code changes and tests.

## Missing-template warning

At the audited commit, `.env.example`/installer coverage is not perfectly aligned with `Settings`; notably production must verify `COOKIE_SECURE` and API-log row limits rather than assuming they were generated.
