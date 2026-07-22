<#
.SYNOPSIS
    Run TraceAI analysis on campaign results.
.DESCRIPTION
    Activates .venv and runs `python -m traceai analyze` with the specified profile.
.PARAMETER Profile
    The environment profile to use. Defaults to 'local'.
#>
[CmdletBinding()]
param(
    [string]$Profile = 'local'
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "=== TraceAI Analyze ===" -ForegroundColor Cyan
Write-Host "Profile: $Profile"
Write-Host ""

# Activate virtual environment
$VenvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $VenvActivate)) {
    Write-Host "[ERROR] Virtual environment not found at .venv\" -ForegroundColor Red
    Write-Host "Create one with: python -m venv .venv"
    exit 1
}
Write-Host "[*] Activating virtual environment..." -ForegroundColor Yellow
& $VenvActivate

# Ensure generated directory exists
$GeneratedDir = Join-Path $ProjectRoot "generated"
if (-not (Test-Path $GeneratedDir)) {
    New-Item -ItemType Directory -Path $GeneratedDir -Force | Out-Null
}

# Run analysis
Write-Host "[*] Running analysis..." -ForegroundColor Yellow
Write-Host "    Command: python -m traceai analyze --profile $Profile" -ForegroundColor DarkGray
Write-Host ""

python -m traceai analyze --profile $Profile
$ExitCode = $LASTEXITCODE

Write-Host ""
if ($ExitCode -eq 0) {
    Write-Host "[OK] Analysis completed successfully." -ForegroundColor Green
} else {
    Write-Host "[FAIL] Analysis failed (exit code: $ExitCode)." -ForegroundColor Red
}

exit $ExitCode
