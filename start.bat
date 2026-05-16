@echo off
chcp 65001 >nul 2>&1
title DevAll Quick Start

:: ==============================================================================
:: DevAll Quick Start Script
:: ==============================================================================

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║       DevAll Quick Start                  ║
echo  ╚══════════════════════════════════════════╝
echo.

:: ------------------------------------------------------------------------------
:: 1. Check Python
:: ------------------------------------------------------------------------------
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python not found. Please install Python 3.12 first.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  [INFO] Python: %PY_VER%

:: ------------------------------------------------------------------------------
:: 2. Check Node.js
:: ------------------------------------------------------------------------------
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Node.js not found. Please install Node.js 18+ first.
    pause
    exit /b 1
)

for /f "tokens=1 delims= " %%v in ('node --version 2^>^&1') do set NODE_VER=%%v
echo  [INFO] Node.js: %NODE_VER%

:: ------------------------------------------------------------------------------
:: 3. Check .env file
:: ------------------------------------------------------------------------------
if not exist ".env" (
    echo  [WARN] .env file not found, creating from .env.example ...
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo  [WARN] .env created. Please edit it with your API_KEY before using LLM features.
    ) else (
        echo  [ERROR] .env.example not found either. Please create .env manually.
        pause
        exit /b 1
    )
) else (
    echo  [INFO] .env file found.
)

:: ------------------------------------------------------------------------------
:: 4. Check / Install uv
:: ------------------------------------------------------------------------------
where uv >nul 2>&1
if %errorlevel% neq 0 (
    echo  [INFO] uv not found, installing ...
    pip install uv
    if %errorlevel% neq 0 (
        echo  [ERROR] Failed to install uv.
        pause
        exit /b 1
    )
)
echo  [INFO] uv is available.

:: ------------------------------------------------------------------------------
:: 5. Install Python dependencies
:: ------------------------------------------------------------------------------
if not exist ".venv" (
    echo  [INFO] Virtual environment not found, running uv sync ...
    uv sync
    if %errorlevel% neq 0 (
        echo  [ERROR] uv sync failed.
        pause
        exit /b 1
    )
) else (
    echo  [INFO] Virtual environment found, skipping uv sync.
)

:: ------------------------------------------------------------------------------
:: 6. Install frontend dependencies
:: ------------------------------------------------------------------------------
if not exist "frontend\node_modules" (
    echo  [INFO] Frontend node_modules not found, running npm install ...
    cd frontend
    call npm install
    cd ..
    if %errorlevel% neq 0 (
        echo  [ERROR] npm install failed.
        pause
        exit /b 1
    )
) else (
    echo  [INFO] Frontend dependencies found, skipping npm install.
)

:: ------------------------------------------------------------------------------
:: 7. Start backend server (port 6400)
:: ------------------------------------------------------------------------------
echo.
echo  [START] Launching backend server on port 6400 ...
start "DevAll Backend" cmd /c "uv run python server_main.py --port 6400"

:: Wait for backend to be ready
echo  [INFO] Waiting for backend to start ...
timeout /t 3 /nobreak >nul

:: ------------------------------------------------------------------------------
:: 8. Start frontend dev server (port 5173)
:: ------------------------------------------------------------------------------
echo  [START] Launching frontend dev server on port 5173 ...
cd frontend
set VITE_API_BASE_URL=http://localhost:6400
start "DevAll Frontend" cmd /c "npx cross-env VITE_API_BASE_URL=http://localhost:6400 npm run dev"
cd ..

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║  Services started successfully!            ║
echo  ╠══════════════════════════════════════════╣
echo  ║  Frontend:  http://localhost:5173          ║
echo  ║  Backend:   http://localhost:6400          ║
echo  ╠══════════════════════════════════════════╣
echo  ║  Press any key to stop all services ...   ║
echo  ╚══════════════════════════════════════════╝
echo.

pause

:: ------------------------------------------------------------------------------
:: 9. Cleanup: kill servers on exit
:: ------------------------------------------------------------------------------
echo  [STOP] Stopping services ...
taskkill /fi "WINDOWTITLE eq DevAll Backend*" >nul 2>&1
taskkill /fi "WINDOWTITLE eq DevAll Frontend*" >nul 2>&1
echo  [INFO] All services stopped. Goodbye!
