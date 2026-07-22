<#
.SYNOPSIS
    Run the traceai doctor diagnostic checks.
.DESCRIPTION
    Activates .venv and runs `python -m traceai doctor` with the specified profile.
    Output is saved to the generated/ directory.
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

Write-Host "=== TraceAI Doctor ===" -ForegroundColor Cyan
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

# Run doctor
Write-Host "[*] Running traceai doctor..." -ForegroundColor Yellow
Write-Host ""

python -m traceai doctor --profile $Profile --output generated
$ExitCode = $LASTEXITCODE

Write-Host ""
if ($ExitCode -eq 0) {
    Write-Host "=== Summary ===" -ForegroundColor Green
    Write-Host "[OK] All diagnostic checks passed." -ForegroundColor Green
} else {
    Write-Host "=== Summary ===" -ForegroundColor Red
    Write-Host "[FAIL] Doctor found issues (exit code: $ExitCode)." -ForegroundColor Red
    Write-Host "Check the generated/ directory for details."
}

exit $ExitCode
