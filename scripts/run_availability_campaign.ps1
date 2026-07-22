<#
.SYNOPSIS
    Run the TraceAI availability campaign.
.DESCRIPTION
    Runs the availability campaign via `python -m traceai campaign availability` with the
    specified profile. Supports --quick mode for faster iteration.
.PARAMETER Profile
    The environment profile to use. Defaults to 'local'.
.PARAMETER Quick
    If specified, runs the campaign in quick mode (fewer iterations).
#>
[CmdletBinding()]
param(
    [string]$Profile = 'local',
    [switch]$Quick
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "=== TraceAI Availability Campaign ===" -ForegroundColor Cyan
Write-Host "Profile: $Profile"
if ($Quick) { Write-Host "Mode: Quick" }
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

# Build command arguments
$CmdArgs = @("campaign", "availability", "--profile", $Profile)
if ($Quick) {
    $CmdArgs += "--quick"
}

Write-Host "[*] Running availability campaign..." -ForegroundColor Yellow
Write-Host "    Command: python -m traceai $($CmdArgs -join ' ')" -ForegroundColor DarkGray
Write-Host ""

python -m traceai @CmdArgs
$ExitCode = $LASTEXITCODE

Write-Host ""
if ($ExitCode -eq 0) {
    Write-Host "[OK] Availability campaign completed successfully." -ForegroundColor Green
} else {
    Write-Host "[FAIL] Availability campaign failed (exit code: $ExitCode)." -ForegroundColor Red
}

exit $ExitCode
