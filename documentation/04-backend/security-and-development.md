# Security and Development Guidelines

## Trust boundaries

OpenBull sits between users, automation clients, broker accounts, market-data providers, PostgreSQL, Redis, and NinjaTrader. Treat every browser request, API body, WebSocket message, webhook, provider payload, and imported symbol as untrusted until the relevant schema, ownership check, and state rule succeeds.

## Required security practices

1. Enforce authentication, ownership, role, trading mode, and workflow state in the backend. A hidden frontend control is not authorization.
2. Store passwords and OpenBull API keys only through the existing Argon2 helpers. Do not implement reversible password storage.
3. Encrypt broker credentials/tokens through `backend.security`; never persist or log plaintext provider secrets.
4. Keep production cookies HttpOnly, `Secure`, and scoped to the supported origin/callback design. Test login, callback, logout, and session revocation after proxy changes.
5. Use parameterized SQL/SQLAlchemy expressions. Do not build statements from request strings.
6. Normalize provider data at the adapter boundary and validate normalized values before order dispatch.
7. Keep live and sandbox dispatch explicit. Every order log must preserve mode and request correlation.
8. Redact authorization headers, passwords, API keys, tokens, secrets, database URLs, webhook tokens, and broker payload fields before logging or screenshots.
9. Rate-limit login, external APIs, order endpoints, and provider retries. Do not retry non-idempotent order calls unless an idempotency/reconciliation design proves the outcome.
10. Review dependency and image updates, run the complete test gate, and back up PostgreSQL before schema-changing releases.

## Secrets and configuration

- `.env` is deployment state and must not be committed.
- `.env.example` contains names/placeholders only.
- `APP_SECRET_KEY` protects JWTs; changing it invalidates sessions.
- `ENCRYPTION_PEPPER` participates in hashing/key derivation; changing it can invalidate passwords and make encrypted rows unreadable.
- `DATABASE_URL` and broker/API credentials are secrets even if access is limited to localhost.
- Example clients use placeholders such as `${OPENBULL_API_KEY}`. Never paste a working key into tests, Bruno collections, documentation, screenshots, or support tickets.

The initial audit found API-key-shaped literals in legacy/manual test assets outside this new documentation tree. Treat them as compromised test material: replace with placeholders and rotate any key that was ever valid.

## Backend contribution rules

- Router: transport, dependency injection, response status.
- Schema: request/response validation.
- Service/domain: reusable business logic and provider-neutral behavior.
- Broker module: provider request, mapping, normalization, and provider errors.
- Model/migration: durable state with explicit constraints/indexes.
- Test: normal case, validation, authorization/ownership, provider failure, retry/concurrency, restart/recovery when relevant.

Keep asynchronous calls non-blocking. Run unavoidable synchronous SDK/database work in the established thread-pool boundary. Reuse shared HTTP/Redis clients; do not create a new connection per tick or quote.

## Frontend contribution rules

- Keep API functions and DTOs out of visual primitives.
- Use TanStack Query for server state and invalidate every affected key after a mutation.
- Keep secrets masked by default and out of URL/query/local storage.
- Preserve keyboard labels, accessible names, focus handling, loading/empty/error states, and responsive layouts.
- Display server messages safely; do not render provider HTML.
- Confirm destructive/live actions and show the active trading mode near the decision.

## Pull-request security checklist

- [ ] No secret or API-key-shaped literal was added.
- [ ] Every new/changed mutation has backend authorization and ownership checks.
- [ ] Live/sandbox behavior and audit fields were reviewed.
- [ ] New inputs have schema and domain validation.
- [ ] Logs and errors are redacted.
- [ ] Migration is idempotent/forward-safe and backup/rollback impact is documented.
- [ ] Unit/build/static tests and documentation validation pass.
- [ ] Screenshots use only documentation data and contain no identifiers or credentials.

## Current security/operational gaps to track

- The production installer must explicitly produce `COOKIE_SECURE=true`; verify the generated `.env` rather than assuming it.
- The health endpoint is liveness-only and does not prove PostgreSQL, Redis, broker, feed, or job readiness.
- One-process background workers/streaming require one Uvicorn worker; scaling without redesign can duplicate jobs or split caches.
- There is no tenant/granular-RBAC model.
- There is no repository CI workflow or automated dependency/secret scan in the current source.

These are documented constraints, not permission to bypass controls. Add remediation to the release plan when the affected area changes.
