# Backup and Restore

## Backup scope

At minimum back up:

- PostgreSQL database.
- `.env` and deployment-specific nginx/systemd configuration.
- TLS/account configuration only through supported Certbot/system backup practices.
- Source commit/tag and any intentionally deployed local integration artifacts.

Redis, frontend build output, Python virtual environment, symbol caches, and generated files are rebuildable, but backing Redis is optional only after verifying no deployment-specific durable use has been added.

## PostgreSQL backup

```bash
sudo install -d -m 700 /secure-backups/openbull
sudo -u postgres pg_dump -Fc openbull \
  > /secure-backups/openbull_$(date +%Y%m%d_%H%M%S).dump
sudo cp --preserve=mode,ownership /var/www/openbull/.env \
  /secure-backups/openbull_env_$(date +%Y%m%d_%H%M%S)
sudo chmod 600 /secure-backups/openbull_env_*
```

Encrypt and copy backups off-host according to organizational policy. Add checksums, monitoring, retention, and a schedule outside this repository; no complete automated/offsite backup job is currently shipped.

## Restore drill

Restore into an isolated database first:

```bash
sudo -u postgres createdb openbull_restore_test
sudo -u postgres pg_restore --clean --if-exists --no-owner \
  -d openbull_restore_test /secure-backups/OPENBULL_BACKUP.dump
sudo -u postgres psql -d openbull_restore_test -c '\dt'
```

Point a non-production OpenBull instance with separate ports/Redis DB at the restored database, run migrations compatible with the source commit, and execute smoke tests. Record restore duration and validated data to establish real RTO/RPO.

## Production restore

1. Announce downtime and stop OpenBull.
2. Capture a final forensic backup when possible.
3. Restore the selected database and matching `.env`/source version.
4. Run only compatible migrations.
5. Start PostgreSQL/Redis/OpenBull/nginx in dependency order.
6. Validate health, sessions, broker re-login requirements, master contracts, strategies, sandbox state, and logs.
7. Revoke/rotate secrets if the incident involved exposure.
