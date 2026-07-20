# 11. Deployment and Operations

## Supported topologies

### Local Windows development

- PostgreSQL on 127.0.0.1:5432.
- Optional but recommended Redis on 127.0.0.1:6379.
- FastAPI on 127.0.0.1:8000; it starts the WebSocket proxy on 127.0.0.1:8765.
- Vite on 127.0.0.1:5173.

See [local setup](local-setup.md).

### Ubuntu production

- Nginx serves `frontend/dist` and terminates TLS.
- systemd runs one Uvicorn worker over `/run/openbull/openbull.sock`.
- The same process listens for market WebSockets on 127.0.0.1:8765.
- PostgreSQL and Redis run locally by default but can be moved through configuration.
- Certbot manages the configured domain certificate.

Production normally does **not** expose backend port 8000.

## Operations guides

- [Local setup](local-setup.md)
- [Configuration reference](configuration.md)
- [Production deployment and update](production-deployment.md)
- [Backup and restore](backup-restore.md)
- [Logging and monitoring](logging-monitoring.md)
- [Incident troubleshooting](../12-testing-troubleshooting/troubleshooting.md)

## Verified operational limitations

- `/health` proves only that FastAPI can answer; it does not validate PostgreSQL, Redis, broker auth, broker data flow, or background workers.
- The current install/update flow has no automatic database rollback.
- Source/update backups are not database backups.
- Automated scheduled/offsite encrypted backups are not implemented by repository scripts.
- Single-worker deployment is required by the current in-process WebSocket/jobs architecture.
- Existing legacy runbook commands that curl port 8000 on production are stale when the Unix-socket deployment is used.
