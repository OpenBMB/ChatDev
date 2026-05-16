<#
.SYNOPSIS
    DevAll Quick Start Script (PowerShell)
.DESCRIPTION
    One-click startup: check dependencies, install if needed, launch backend + frontend.
    Press Ctrl+C to stop all services.
#>

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host ""
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host "        DevAll Quick Start" -ForegroundColor Cyan
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------------------------
# 1. Check Python
# ------------------------------------------------------------------------------
try {
    $pyVer = python --version 2>&1
    Write-Host "  [INFO] Python: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Python not found. Please install Python 3.12 first." -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------------------------
# 2. Check Node.js
# ------------------------------------------------------------------------------
try {
    $nodeVer = node --version 2>&1
    Write-Host "  [INFO] Node.js: $nodeVer" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Node.js not found. Please install Node.js 18+ first." -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------------------------
# 3. Check .env file
# ------------------------------------------------------------------------------
if (-not (Test-Path ".env")) {
    Write-Host "  [WARN] .env not found, creating from .env.example ..." -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "  [WARN] .env created. Please edit it with your API_KEY before using LLM features." -ForegroundColor Yellow
    } else {
        Write-Host "  [ERROR] .env.example not found. Please create .env manually." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  [INFO] .env file found." -ForegroundColor Green
}

# ------------------------------------------------------------------------------
# 4. Check / Install uv
# ------------------------------------------------------------------------------
$uvAvailable = $null -ne (Get-Command "uv" -ErrorAction SilentlyContinue)
if (-not $uvAvailable) {
    Write-Host "  [INFO] uv not found, installing ..." -ForegroundColor Yellow
    pip install uv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERROR] Failed to install uv." -ForegroundColor Red
        exit 1
    }
}
Write-Host "  [INFO] uv is available." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 5. Install Python dependencies
# ------------------------------------------------------------------------------
if (-not (Test-Path ".venv")) {
    Write-Host "  [INFO] Virtual environment not found, running uv sync ..." -ForegroundColor Yellow
    uv sync
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERROR] uv sync failed." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  [INFO] Virtual environment found, skipping uv sync." -ForegroundColor Green
}

# ------------------------------------------------------------------------------
# 6. Install frontend dependencies
# ------------------------------------------------------------------------------
if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "  [INFO] Frontend node_modules not found, running npm install ..." -ForegroundColor Yellow
    Push-Location frontend
    npm install
    Pop-Location
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERROR] npm install failed." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  [INFO] Frontend dependencies found, skipping npm install." -ForegroundColor Green
}

# ------------------------------------------------------------------------------
# 7. Start backend server
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "  [START] Launching backend server on port 6400 ..." -ForegroundColor Cyan
$backendJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    uv run python server_main.py --port 6400 2>&1
}

# Wait briefly for backend
Write-Host "  [INFO] Waiting for backend to start ..." -ForegroundColor DarkGray
Start-Sleep -Seconds 3

# ------------------------------------------------------------------------------
# 8. Start frontend dev server
# ------------------------------------------------------------------------------
Write-Host "  [START] Launching frontend dev server on port 5173 ..." -ForegroundColor Cyan
$frontendJob = Start-Job -ScriptBlock {
    Set-Location "$using:PWD\frontend"
    $env:VITE_API_BASE_URL = "http://localhost:6400"
    npx cross-env VITE_API_BASE_URL=http://localhost:6400 npm run dev 2>&1
}

Start-Sleep -Seconds 2

Write-Host ""
Write-Host "  ========================================" -ForegroundColor Green
Write-Host "    Services started successfully!" -ForegroundColor Green
Write-Host "  ----------------------------------------" -ForegroundColor Green
Write-Host "    Frontend:  http://localhost:5173" -ForegroundColor White
Write-Host "    Backend:   http://localhost:6400" -ForegroundColor White
Write-Host "  ----------------------------------------" -ForegroundColor Green
Write-Host "    Press Ctrl+C to stop all services" -ForegroundColor DarkGray
Write-Host "  ========================================" -ForegroundColor Green
Write-Host ""

# ------------------------------------------------------------------------------
# 9. Monitor jobs & cleanup on exit
# ------------------------------------------------------------------------------
try {
    while ($true) {
        # Print backend output
        $backendOut = Receive-Job -Job $backendJob -ErrorAction SilentlyContinue 2>$null
        if ($backendOut) { $backendOut | ForEach-Object { Write-Host "  [BACKEND] $_" -ForegroundColor DarkGray } }

        # Print frontend output
        $frontendOut = Receive-Job -Job $frontendJob -ErrorAction SilentlyContinue 2>$null
        if ($frontendOut) { $frontendOut | ForEach-Object { Write-Host "  [FRONTEND] $_" -ForegroundColor DarkGray } }

        # Check if jobs are still running
        if ($backendJob.State -eq "Failed" -or $backendJob.State -eq "Completed") {
            Write-Host "  [WARN] Backend server stopped unexpectedly." -ForegroundColor Yellow
            break
        }
        if ($frontendJob.State -eq "Failed" -or $frontendJob.State -eq "Completed") {
            Write-Host "  [WARN] Frontend server stopped unexpectedly." -ForegroundColor Yellow
            break
        }

        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host ""
    Write-Host "  [STOP] Stopping services ..." -ForegroundColor Yellow
    Stop-Job -Job $backendJob -ErrorAction SilentlyContinue
    Stop-Job -Job $frontendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $backendJob -Force -ErrorAction SilentlyContinue
    Remove-Job -Job $frontendJob -Force -ErrorAction SilentlyContinue
    Write-Host "  [INFO] All services stopped. Goodbye!" -ForegroundColor Green
}
