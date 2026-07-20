# Local Environment Setup

## Prerequisites

- Windows PowerShell or Command Prompt.
- Python 3.12 or later.
- Node.js 20 or later and npm.
- PostgreSQL 15 or later.
- Redis 7 or a compatible reachable Redis service; the app has fallbacks but live performance/diagnostics should include Redis.
- Git.

## One-time setup

```bat
cd /d D:\openbull
py -3.12 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install uv
uv sync
copy .env.example .env
```

Generate different values for `APP_SECRET_KEY` and `ENCRYPTION_PEPPER` and configure a local PostgreSQL database. Never reuse documentation/example secrets.

```bat
python migrate_all.py
cd frontend
npm ci
```

The checked-in `run-local.bat` is the convenience launcher; `RUN_LOCAL.txt` contains copy/paste commands. Review its service checks before using it on a machine with non-default PostgreSQL paths.

## Start manually

Terminal 1:

```bat
cd /d D:\openbull
call .venv\Scripts\activate.bat
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2:

```bat
cd /d D:\openbull\frontend
npm run dev
```

Open `http://127.0.0.1:5173`. Use one hostname consistently for browser, frontend URL, CORS, and broker callback configuration.

## Verification

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Get-NetTCPConnection -State Listen |
  Where-Object LocalPort -in 5432,6379,8000,8765,5173
```

Expected backend startup logs include database tables ready, workers started, broker plugins loaded, and WebSocket proxy listening. A broker stream is not expected until a user authenticates and a client requests symbols.
