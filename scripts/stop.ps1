$ErrorActionPreference = "SilentlyContinue"

$Root = Split-Path -Parent $PSScriptRoot
$StateDir = Join-Path $Root ".run"
$BackendPidFile = Join-Path $StateDir "backend.pid"
$FrontendPidFile = Join-Path $StateDir "frontend.pid"

function Stop-PidFile {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return
    }

    $pidValue = Get-Content $Path | Select-Object -First 1
    if ($pidValue) {
        Stop-Process -Id ([int]$pidValue) -Force
    }
    Remove-Item $Path -Force
}

Stop-PidFile -Path $FrontendPidFile
Stop-PidFile -Path $BackendPidFile

Write-Host "MovieDev dev services stopped."
