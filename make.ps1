param (
    [Parameter(Position=0)]
    [string]$Command = "help"
)
Set-StrictMode -version latest;
$ErrorActionPreference = 'Stop'

function Exec {
    param([scriptblock]$CommandBlock)
    & $CommandBlock
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
function Show-Help {
    $makefile = Join-Path $PSScriptRoot "Makefile"
    if (-not (Test-Path $makefile)) {
        Write-Host "Makefile not found." -ForegroundColor Yellow
        return
    }

    $commands = @()
    foreach ($line in Get-Content $makefile) {
        if ($line -match '^([a-zA-Z_-]+):.*?## (.*)$') {
            $commands += [PSCustomObject]@{
                Name = $matches[1]
                Desc = $matches[2]
            }
        }
    }

    foreach ($cmd in ($commands | Sort-Object Name)) {
        Write-Host ("{0,-20} {1}" -f $cmd.Name, $cmd.Desc)
    }
}

function Start-Server {
    Write-Host "Starting server in background..."
    Start-Process -NoNewWindow uv -ArgumentList "run", "python", "server_main.py", "--port", "6400"
}

function Start-Client {
    Write-Host "Starting frontend server..."
    $env:VITE_API_BASE_URL="http://localhost:6400"
    Exec { npm run dev --prefix frontend }
}

function Stop-Servers {
    try {
        Push-Location (Join-Path $PSScriptRoot "frontend")
        try {
            Write-Host "Stopping backend server (port 6400)..."
            npx kill-port 6400
        } catch { Write-Host "  Port 6400: nothing to stop" -ForegroundColor DarkGray }
        try {
            Write-Host "Stopping frontend server (port 5173)..."
            npx kill-port 5173
        } catch { Write-Host "  Port 5173: nothing to stop" -ForegroundColor DarkGray }
    } finally {
        Pop-Location
    }
}

function Sync-Graphs {
    Exec { uv run python tools/sync_vuegraphs.py }
}

function Validate-Yamls {
    Exec { uv run python tools/validate_all_yamls.py }
}

function Test-Backend {
    Exec { uv run pytest -v }
}

function Lint-Backend {
    Exec { uvx ruff check . }
}

switch ($Command) {
    "dev" {
        Start-Server
        Start-Client
    }
    "server" {
        Start-Server
    }
    "client" {
        Start-Client
    }
    "stop" {
        Stop-Servers
    }
    "sync" {
        Sync-Graphs
    }
    "validate-yamls" {
        Validate-Yamls
    }
    "check-backend" {
        Test-Backend
        Lint-Backend
    }
    "backend-tests" {
        Test-Backend
    }
    "backend-lint" {
        Lint-Backend
    }
    "help" {
        Show-Help
    }
    default {
        Write-Error "Unknown command: $Command" -ErrorAction Continue
        Show-Help
        exit 1
    }
}
