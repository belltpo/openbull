# Troubleshooting Runbook

## Backend does not start

Check PostgreSQL first. `Connect call failed ... 5432` means the configured database listener is unavailable or credentials/host are wrong.

```powershell
Get-NetTCPConnection -State Listen | Where-Object LocalPort -eq 5432
Get-Service *postgres*
```

Production:

```bash
sudo systemctl status postgresql openbull --no-pager -l
sudo journalctl -u openbull -n 300 --no-pager
```

## Frontend proxy `ECONNREFUSED 127.0.0.1:8000`

Vite is running but FastAPI is not listening locally. Start the backend and verify `/health`. On production, port 8000 is normally absent because nginx uses the Unix socket.

## Pages show no live values

1. Confirm broker configuration **and** current broker authentication.
2. Confirm provider data subscription/segment.
3. Confirm master-contract status and exact symbol/exchange.
4. Check WebSocket authentication and subscribe acknowledgement.
5. Inspect `/api/websocket/health` and adapter logs.
6. Check Redis, but remember Redis failure should fall back rather than erase PostgreSQL state.
7. Check exchange market session and whether the instrument is actually trading.

## Web and NinjaTrader fail together

They share OpenBull's active broker token, quote services, adapter, and market cache. Diagnose the broker↔OpenBull path first. NinjaTrader Quick Order's OpenBull API key is separate from the broker token.

## Dhan rate-limit/auth symptoms

- Invalid/expired token: re-login once and ensure the stream/cache context uses the new token.
- Data entitlement error: activate provider Data API access.
- 429/connection code: stop duplicate clients/poll loops and allow backoff.
- Connected but stale: verify symbol subscription and new ticks before forcing repeated reconnects.

## Redis warnings

```bash
sudo systemctl status redis-server --no-pager -l
sudo redis-cli ping
sudo redis-cli info memory
```

Errors mentioning a Future attached to another loop indicate an asyncio Redis client escaped its owning event loop. Current code uses loop-scoped clients; verify the deployed commit and do not cache a Redis client in a cross-thread global.

## Deployment update blocked by dirty files

Do not delete unknown live changes. Capture `git status`, back up `.env` and PostgreSQL, and use the current root updater's backup/stash workflow. Inspect the generated stash/source backup after success. Avoid `git reset --hard` unless an authorized rollback procedure explicitly calls for it and backups exist.

## Production 502

```bash
sudo systemctl status openbull nginx --no-pager -l
sudo ss -lxnp | grep /run/openbull/openbull.sock
sudo nginx -t
sudo tail -n 200 /var/log/nginx/error.log
sudo journalctl -u openbull -n 300 --no-pager
```

The likely boundary is nginx→Uvicorn Unix socket, not port 8000.
