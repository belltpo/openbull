@echo off
setlocal

rem OpenBull local development launcher.
rem Run from Command Prompt with:  D:\openbull\run-local.bat

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "VENV=%ROOT%\.venv"
set "POSTGRES_SERVICE=postgresql-x64-18"

if not exist "%VENV%\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found at "%VENV%".
    echo Create it and install the backend dependencies first.
    exit /b 1
)

if not exist "%VENV%\Scripts\python.exe" (
    echo [ERROR] Python was not found in "%VENV%\Scripts".
    exit /b 1
)

"%VENV%\Scripts\python.exe" -c "import uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Uvicorn is not installed in the OpenBull virtual environment.
    echo Activate the venv and install the backend dependencies first.
    exit /b 1
)

if not exist "%ROOT%\frontend\package.json" (
    echo [ERROR] Frontend package.json was not found.
    exit /b 1
)

where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm was not found. Install Node.js and reopen this terminal.
    exit /b 1
)

if not exist "%ROOT%\frontend\node_modules" (
    echo [ERROR] Frontend packages are not installed.
    echo Run: cd /d "%ROOT%\frontend" ^&^& npm install
    exit /b 1
)

sc.exe query "%POSTGRES_SERVICE%" 2>nul | findstr /C:"RUNNING" >nul
if errorlevel 1 (
    echo [ERROR] PostgreSQL service "%POSTGRES_SERVICE%" is not running.
    echo Open PowerShell as Administrator and run:
    echo     Start-Service %POSTGRES_SERVICE%
    echo Then run this file again.
    exit /b 1
)

echo Starting OpenBull backend and frontend in separate terminals...
start "OpenBull Backend" /D "%ROOT%" cmd /k "call .venv\Scripts\activate.bat && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"
start "OpenBull Frontend" /D "%ROOT%\frontend" cmd /k "call ..\.venv\Scripts\activate.bat && npm.cmd run dev"

echo.
echo Frontend: http://127.0.0.1:5173/
echo Backend:  http://127.0.0.1:8000/
echo API docs: http://127.0.0.1:8000/docs
echo Close the two opened terminals or press Ctrl+C in each one to stop OpenBull.

endlocal
exit /b 0
