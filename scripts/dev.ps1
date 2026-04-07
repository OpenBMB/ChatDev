$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$StateDir = Join-Path $Root ".run"
$LogDir = Join-Path $Root "logs"
$BackendPidFile = Join-Path $StateDir "backend.pid"
$FrontendPidFile = Join-Path $StateDir "frontend.pid"

$BackendHost = if ($env:BACKEND_HOST) { $env:BACKEND_HOST } else { "127.0.0.1" }
$BackendPort = if ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "6400" }
$FrontendHost = if ($env:FRONTEND_HOST) { $env:FRONTEND_HOST } else { "127.0.0.1" }
$FrontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "5173" }
$BackendReload = if ($env:BACKEND_RELOAD) { $env:BACKEND_RELOAD } else { "0" }

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

& (Join-Path $PSScriptRoot "stop.ps1") | Out-Null

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "Missing required command: uv"
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Missing required command: node"
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Missing required command: npm"
}

$BackendLog = Join-Path $LogDir "dev-backend.log"
$FrontendLog = Join-Path $LogDir "dev-frontend.log"

$backendCommand = "uv run python server_main.py --host $BackendHost --port $BackendPort"
if ($BackendReload -eq "1") {
    $backendCommand += " --reload"
}

$backendProcess = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", $backendCommand `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $BackendLog `
    -RedirectStandardError $BackendLog `
    -PassThru

$frontendCommand = "set VITE_API_BASE_URL=http://$BackendHost`:$BackendPort&& npm run dev -- --host $FrontendHost --port $FrontendPort"
$frontendProcess = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", $frontendCommand `
    -WorkingDirectory (Join-Path $Root "frontend") `
    -RedirectStandardOutput $FrontendLog `
    -RedirectStandardError $FrontendLog `
    -PassThru

$backendProcess.Id | Set-Content -Path $BackendPidFile
$frontendProcess.Id | Set-Content -Path $FrontendPidFile

Write-Host "MovieDev dev environment is starting..."
Write-Host "Backend:  http://$BackendHost`:$BackendPort"
Write-Host "Frontend: http://$FrontendHost`:$FrontendPort"
Write-Host "Logs:"
Write-Host "  $BackendLog"
Write-Host "  $FrontendLog"
Write-Host "Press Ctrl+C to stop both services."

try {
    while ($true) {
        if ($backendProcess.HasExited) {
            throw "Backend process exited unexpectedly. Check $BackendLog"
        }
        if ($frontendProcess.HasExited) {
            throw "Frontend process exited unexpectedly. Check $FrontendLog"
        }
        Start-Sleep -Seconds 2
    }
}
finally {
    & (Join-Path $PSScriptRoot "stop.ps1") | Out-Null
}
