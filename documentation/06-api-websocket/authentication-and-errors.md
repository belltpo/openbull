# Authentication and Error Handling

## Browser authentication

1. Initial setup hashes the password with Argon2 plus the configured pepper and creates the first admin.
2. Login verifies credentials, records a login attempt, creates an `active_sessions` row, and issues a JWT in an HttpOnly cookie.
3. Protected requests decode the JWT and require its JTI to match a current active session.
4. Logout removes/revokes session state and clears cached user/broker contexts.

Production **must** set `COOKIE_SECURE=true`; local HTTP must leave that setting false. The application default is false, and the audited installer does not currently guarantee the production override, so operators must verify it in `.env` before go-live. SameSite is configured to permit the supported broker callback flow while limiting cross-site cookie use.

## OpenBull API keys

API keys are generated per user. Verification uses a stored Argon2 hash; an encrypted copy supports the authenticated owner/API-helper features. Treat the plaintext key as a password. Rotating it invalidates integrations such as NinjaTrader until they are updated.

## Broker authentication

Broker application credentials and broker access tokens are different:

- `broker_configs` stores encrypted app/client configuration and redirect metadata.
- `broker_auth` stores the current encrypted broker access/feed token and revocation state.

A configured broker is not necessarily authenticated. Live REST/streaming requires a non-revoked, provider-valid token and required provider subscriptions/segments.

## Authorization errors

| HTTP status | Typical meaning |
|---:|---|
| 400 | Invalid domain input, unsupported symbol/configuration, or workflow state |
| 401 | Missing/invalid application session or API key |
| 403 | Admin required, broker not authenticated, strategy live mode not enabled, or provider permission denied |
| 404 | Resource absent or deliberately hidden by ownership enforcement |
| 409 | Conflicting active phase/run/state or duplicate operation |
| 422 | Pydantic request validation failure |
| 429 | OpenBull or broker rate limit/backoff |
| 500/502/503 | Internal failure or upstream provider/service unavailable |

Broker error payloads are normalized where possible. The frontend's broker-issue handler distinguishes actions such as re-login, data-subscription activation, and rate-limit backoff.

## Secret handling

- Never place API keys/tokens in query strings, screenshots, Git, or logs.
- Use shared redaction utilities for structured and free-text logs.
- Do not return saved secrets to the browser; credential endpoints return configured/masked state.
- Rotate application secrets and broker tokens through planned procedures because changing the encryption pepper can make existing encrypted data unreadable.
