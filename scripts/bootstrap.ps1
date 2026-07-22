<#
.SYNOPSIS
    Bootstrap the traceai development environment.
.DESCRIPTION
    Activates .venv, installs pip-tools, compiles requirements, installs packages,
    installs the package in editable mode, detects PyTorch CUDA support, and saves
    a bootstrap_report.json to generated/.
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

Write-Host "=== TraceAI Bootstrap ===" -ForegroundColor Cyan
Write-Host "Profile: $Profile"
Write-Host ""

# Activate virtual environment
$VenvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $VenvActivate)) {
    Write-Host "[ERROR] Virtual environment not found at .venv\" -ForegroundColor Red
    Write-Host "Create one with: python -m venv .venv"
    exit 1
}
Write-Host "[1/6] Activating virtual environment..." -ForegroundColor Yellow
& $VenvActivate

# Install pip-tools
Write-Host "[2/6] Installing pip-tools..." -ForegroundColor Yellow
python -m pip install --quiet --upgrade pip pip-tools
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Failed to install pip-tools" -ForegroundColor Red; exit 1 }

# Compile requirements
Write-Host "[3/6] Compiling requirements..." -ForegroundColor Yellow
$RequirementsIn = Join-Path $ProjectRoot "requirements.in"
$RequirementsTxt = Join-Path $ProjectRoot "requirements.txt"
if (Test-Path $RequirementsIn) {
    pip-compile --quiet --output-file $RequirementsTxt $RequirementsIn
    if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Failed to compile requirements" -ForegroundColor Red; exit 1 }
} else {
    Write-Host "  No requirements.in found, skipping compilation." -ForegroundColor DarkYellow
}

# Install packages
Write-Host "[4/6] Installing packages..." -ForegroundColor Yellow
if (Test-Path $RequirementsTxt) {
    pip-sync $RequirementsTxt
    if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Failed to sync packages" -ForegroundColor Red; exit 1 }
} else {
    Write-Host "  No requirements.txt found, skipping sync." -ForegroundColor DarkYellow
}

# Install package in editable mode
Write-Host "[5/6] Installing package in editable mode..." -ForegroundColor Yellow
python -m pip install --quiet -e .
if ($LASTEXITCODE -ne 0) { Write-Host "[ERROR] Failed to install package in editable mode" -ForegroundColor Red; exit 1 }

# Detect PyTorch CUDA
Write-Host "[6/6] Detecting PyTorch CUDA support..." -ForegroundColor Yellow
$CudaAvailable = $false
$CudaVersion = "N/A"
$PyTorchVersion = "N/A"
try {
    $torchInfo = python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda if torch.cuda.is_available() else 'N/A')" 2>&1
    $lines = $torchInfo -split "`n"
    if ($lines.Count -ge 3) {
        $PyTorchVersion = $lines[0].Trim()
        $CudaAvailable = $lines[1].Trim() -eq "True"
        $CudaVersion = $lines[2].Trim()
    }
} catch {
    Write-Host "  PyTorch not installed or detection failed." -ForegroundColor DarkYellow
}

Write-Host "  PyTorch Version: $PyTorchVersion"
Write-Host "  CUDA Available:  $CudaAvailable"
Write-Host "  CUDA Version:    $CudaVersion"

# Save bootstrap report
$GeneratedDir = Join-Path $ProjectRoot "generated"
if (-not (Test-Path $GeneratedDir)) {
    New-Item -ItemType Directory -Path $GeneratedDir -Force | Out-Null
}

$Report = @{
    timestamp        = (Get-Date -Format "o")
    profile          = $Profile
    python_version   = (python --version 2>&1).ToString().Replace("Python ", "")
    pytorch_version  = $PyTorchVersion
    cuda_available   = $CudaAvailable
    cuda_version     = $CudaVersion
    pip_tools        = $true
    editable_install = $true
}

$ReportPath = Join-Path $GeneratedDir "bootstrap_report.json"
$Report | ConvertTo-Json -Depth 4 | Set-Content -Path $ReportPath -Encoding UTF8
Write-Host ""
Write-Host "[OK] Bootstrap complete. Report saved to: $ReportPath" -ForegroundColor Green
exit 0
