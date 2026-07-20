# Getting Started and Broker Access

## Purpose and access

This workflow creates or restores an OpenBull browser session, connects the user's configured broker session, and confirms the instance-wide Live/Sandbox mode. Initial Setup is public only before the first user exists. Login is public. Broker selection/configuration requires an authenticated OpenBull session. Only an administrator can change global trading mode.

## Screenshots

- [Initial Setup](../assets/screenshots/setup/00-complete-page.png)
- [Login](../assets/screenshots/login/00-complete-page.png)
- [Broker selection](../assets/screenshots/broker-select/00-complete-page.png)
- [Broker Configuration](../assets/screenshots/broker-config/00-complete-page.png)
- [01 — opened broker selector](../assets/screenshots/broker-config/01-open-broker-selector.png)
- [Dhan token login](../assets/screenshots/broker-dhan-token/00-complete-page.png)

## Fields and controls

| Page | Field/control | Meaning and rule |
|---|---|---|
| Setup | Username, email | Required first-admin identity. Setup is rejected after a user exists. |
| Setup | Password/Confirm | Current UI precheck is six characters, but the backend requires eight; use at least eight. Values must match and the server hashes the password. |
| Login | Username/Password | Required OpenBull credentials, not broker credentials. Password visibility changes display only. |
| Broker Select | Configure/Login | Configure saves provider app credentials; Login creates/renews provider authentication. They are distinct states. |
| Broker Config | Provider fields | Required fields differ by broker. Blank saved-secret behavior is provider/backend specific. |
| Dhan token | Client ID/Access Token | Client ID is required; current UI requires a token longer than 50 characters. |
| Header | Live/Sandbox | Shows global dispatch mode. Mutation is admin-only server-side. |

## Workflow

1. On a new database, open `/setup`, enter all four fields, and create the administrator.
2. Otherwise open `/login`, enter the OpenBull username/password, and select **Sign In**.
3. If redirected to Broker Select, configure the intended broker if needed, then complete OAuth, TOTP, or the supported Dhan token path.
4. Wait until master-contract status completes before using symbol/derivative selectors.
5. Confirm the global mode in the header. Use Sandbox for initial verification.
6. Open Dashboard and verify that account panels render without an authentication error.

## Expected result

The browser has an HttpOnly application cookie, `/auth/me` returns the current user and broker context, and guarded routes render. Broker configuration alone does not guarantee a valid market-data or order token.

## Validation, permissions, and errors

| Symptom | Cause/check |
|---|---|
| Setup returns 403 | At least one user already exists; use Login. |
| Login returns 401/429 | Invalid credentials or login rate limit. Do not retry in a tight loop. |
| Redirected to Broker Select | No current non-revoked broker auth exists. |
| “Configured” but no data | App credentials exist, but token/entitlement/symbol stream is absent or expired. |
| Mode switch returns 403 | Only `User.is_admin` may call the mode mutation. |
| Symbols/expiries empty | Master contract is incomplete, exchange selection is wrong, or provider download failed. |

## APIs and dependencies

`GET /auth/check-setup`, `POST /auth/setup`, `POST /auth/login`, `GET /auth/me`, broker configuration/list/login routes, `GET/POST /web/trading-mode`, PostgreSQL, encryption settings, the selected broker, and master-contract loader. See [Authentication](../06-api-websocket/authentication-and-errors.md) and [Broker integrations](../07-integrations/brokers.md).
