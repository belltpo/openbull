# Documentation Traceability Matrix

| Documentation area | Primary source | Generated/runtime evidence | Status |
|---|---|---|---|
| Frontend routes | `frontend/src/App.tsx` | `inventories/frontend-routes.md` | Generated |
| HTTP APIs | `backend/main.py`, `backend/routers/`, `backend/api/` | `inventories/openapi.json`, `inventories/api-endpoints.md` | Generated |
| WebSocket protocols | `backend/websocket_proxy/`, `backend/strategy/ws.py` | Protocol guide and integration tests | Documented/tested |
| Database | `backend/models/`, Alembic revisions | `inventories/database-schema.md` | Generated |
| Environment | `backend/config.py`, `.env.example`, install scripts | `inventories/environment-variables.md` | Generated |
| User manuals | Page/component/API source | 40 route + 17 action captures and manifest | Documented; live-provider outcomes externally pending |
| Deployment | Root and `install/` scripts | Build/check and named-server runbook | Documented; production host evidence is deployment-specific |
| Integrations | `backend/broker/`, `integrations/` | Provider guides and NinjaTrader static checks | Documented; provider entitlements externally pending |
