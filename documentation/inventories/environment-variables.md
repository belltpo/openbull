# Generated Environment Variable Inventory

> Generated from `backend.config.Settings`. Values from `.env` are never read or emitted.

| Variable | Type | Sensitive | Default/requirement | Purpose source |
|---|---|---:|---|---|
| `APP_SECRET_KEY` | `str` | yes | Required; generate a unique secret | `backend/config.py` |
| `ENCRYPTION_PEPPER` | `str` | yes | Required; generate a unique secret | `backend/config.py` |
| `DATABASE_URL` | `str` | yes | Required; generate a unique secret | `backend/config.py` |
| `BACKEND_HOST` | `str` | no | `127.0.0.1` | `backend/config.py` |
| `BACKEND_PORT` | `int` | no | `8000` | `backend/config.py` |
| `FRONTEND_URL` | `str` | no | `http://127.0.0.1:5173` | `backend/config.py` |
| `FLASK_DEBUG` | `bool` | no | `False` | `backend/config.py` |
| `CORS_ORIGINS` | `str` | no | `http://127.0.0.1:5173,http://localhost:5173` | `backend/config.py` |
| `VALID_BROKERS` | `str` | no | `upstox,zerodha` | `backend/config.py` |
| `LOG_LEVEL` | `str` | no | `INFO` | `backend/config.py` |
| `LOG_TO_FILE` | `bool` | no | `True` | `backend/config.py` |
| `LOG_DIR` | `str` | no | `logs` | `backend/config.py` |
| `LOG_COLORS` | `bool` | no | `True` | `backend/config.py` |
| `LOG_FILE_MAX_MB` | `int` | no | `10` | `backend/config.py` |
| `LOG_FILE_BACKUP_COUNT` | `int` | no | `9` | `backend/config.py` |
| `ERROR_LOG_DB_MAX_ROWS` | `int` | no | `50000` | `backend/config.py` |
| `API_LOG_DB_MAX_ROWS` | `int` | no | `100000` | `backend/config.py` |
| `LOGIN_RATE_LIMIT_MIN` | `str` | no | `5 per minute` | `backend/config.py` |
| `LOGIN_RATE_LIMIT_HOUR` | `str` | no | `25 per hour` | `backend/config.py` |
| `API_RATE_LIMIT` | `str` | no | `50 per second` | `backend/config.py` |
| `ORDER_RATE_LIMIT` | `str` | no | `10 per second` | `backend/config.py` |
| `SESSION_EXPIRY_TIME` | `str` | no | `03:00` | `backend/config.py` |
| `COOKIE_SECURE` | `bool` | no | `False` | `backend/config.py` |
| `WEBSOCKET_HOST` | `str` | no | `127.0.0.1` | `backend/config.py` |
| `WEBSOCKET_PORT` | `int` | no | `8765` | `backend/config.py` |
| `WEBSOCKET_URL` | `str` | no | `ws://127.0.0.1:8765` | `backend/config.py` |
| `ZMQ_HOST` | `str` | no | `127.0.0.1` | `backend/config.py` |
| `ZMQ_PORT` | `int` | no | `5555` | `backend/config.py` |
| `REDIS_URL` | `str` | no | `redis://127.0.0.1:6379/0` | `backend/config.py` |
| `MAX_SYMBOLS_PER_WEBSOCKET` | `int` | no | `1000` | `backend/config.py` |
| `MAX_WEBSOCKET_CONNECTIONS` | `int` | no | `3` | `backend/config.py` |
| `ENABLE_CONNECTION_POOLING` | `bool` | no | `True` | `backend/config.py` |

Deployment scripts also derive production values such as HTTPS frontend/CORS URLs, secure cookies, WebSocket public URL, database credentials, and service paths. See the deployment configuration guide before editing a live `.env`.
