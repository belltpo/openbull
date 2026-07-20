# Production Deployment and Update

## Fresh Ubuntu deployment

Use the root entrypoint:

```bash
cd /var/www/openbull
sudo chmod +x install.sh install/*.sh
sudo ./install.sh
```

Select fresh install and provide the actual domain, SSL notification email, repository/branch, app directory, service name, PostgreSQL details, and requested build/migration/health actions. The underlying installer provisions system packages, Node, PostgreSQL, Redis, nginx, Certbot, firewall, database, `.env`, systemd unit, nginx site, and frontend build.

Important current behavior: in fresh-install mode, the root `install.sh` pipes only the domain into `install/install.sh`. Its collected install-dependencies, migration, frontend-build, permission, restart, nginx, and health-check choices are **not propagated as child-installer switches**. Treat those prompts as update/build controls, not as a guarantee that fresh-install child steps were skipped. Verify every resulting service/artifact explicitly. This is an audited implementation limitation, not intended behavior.

Review generated files before declaring success:

```bash
sudo systemctl cat openbull
sudo nginx -T
sudo sed -n '1,220p' /var/www/openbull/.env | sed -E 's/(SECRET|PASSWORD|KEY|TOKEN)=.*/\1=[REDACTED]/I'
sudo ss -lxnp | grep /run/openbull/openbull.sock
sudo ss -lntp | grep -E ':(5432|6379|8765)\b'
```

Do not use the installer default database password. Ensure `.env` and any file containing a database URL are not world-readable. The audited installer writes connection material into `alembic.ini`; harden permissions and consider migrating to environment-only Alembic configuration.

## Update existing deployment

The current root updater preserves deployment values from the existing `.env`, creates a source-tree backup, stashes dirty tracked/untracked changes, fast-forwards the selected branch, restores/preserves `.env`, runs dependencies/migrations/build, fixes ownership, restarts service, reloads nginx, and performs a public health check.

Before update:

```bash
cd /var/www/openbull
sudo git status --short
sudo -u postgres pg_dump -Fc openbull > /secure-backups/openbull_preupdate_$(date +%Y%m%d_%H%M%S).dump
sudo cp --preserve=mode,ownership .env /secure-backups/openbull_env_$(date +%Y%m%d_%H%M%S)
sudo ./install.sh
```

The updater's source backup is not a PostgreSQL backup. A migration/build/restart failure does not automatically roll back schema/data.

## Post-deploy verification

```bash
sudo systemctl status openbull redis-server nginx postgresql --no-pager -l
sudo journalctl -u openbull --since '15 minutes ago' --no-pager
curl --fail --silent --show-error --unix-socket /run/openbull/openbull.sock http://localhost/health
curl --fail --silent --show-error https://YOUR_DOMAIN/health
sudo nginx -t
sudo certbot certificates
```

Confirm the public health body is JSON, not the SPA HTML fallback. Then perform authenticated database, broker REST, WebSocket, sandbox, and background-worker smoke tests; liveness alone is insufficient.

## Rollback

Application rollback requires a compatible source commit, dependency/frontend rebuild, service restart, and—when migrations are incompatible—a tested database restore or explicit down migration. Never point old code at a newly migrated database without compatibility review.
