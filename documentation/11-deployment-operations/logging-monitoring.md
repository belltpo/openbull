# Logging and Monitoring

## Log destinations

| Destination | Content | Default bounds/source |
|---|---|---|
| `openbull.log` | Application logs all configured levels | Rotating, 10 MB active × active plus 9 backups by default |
| `openbull-error.log` | Warning and error logs | Same rotation defaults |
| systemd `backend.log`/`backend.error.log` in installer | Service stdout/stderr | Host logrotate configuration |
| `api_logs` table | Authenticated API request audit | Default maximum 100,000 rows |
| `error_logs` table | DB-backed warning/error sink | Default maximum 50,000 rows |
| nginx access/error logs | Public proxy traffic and upstream failures | Distribution/logrotate policy |

## Useful commands

```bash
sudo systemctl status openbull redis-server postgresql nginx --no-pager -l
sudo journalctl -u openbull --since '30 minutes ago' --no-pager
sudo tail -F /var/log/openbull/openbull.log /var/log/openbull/openbull-error.log
sudo tail -F /var/log/nginx/access.log /var/log/nginx/error.log
sudo redis-cli ping
sudo -u postgres psql -d openbull -c 'select now();'
```

For market data:

```bash
sudo tail -n 1000 /var/log/openbull/openbull.log \
  | grep -Ei 'adapter|dhan|upstox|zerodha|fyers|angel|subscribe|market.data|feed stale|redis|auth'
```

## Monitoring requirements not shipped

The repository does not ship Prometheus/Grafana alerts, synthetic authenticated checks, backup-success alerts, certificate-expiry alerts, database-capacity alerts, or broker entitlement/token-expiry monitoring. Operators must implement these externally and document thresholds for their deployment.
