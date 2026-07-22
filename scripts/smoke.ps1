<#
.SYNOPSIS
    Run smoke tests: unit tests and minimal inference verification.
.DESCRIPTION
    Runs the unit test suite via pytest, then performs a minimal inference test
    by loading the GPT-2 model, generating one response, and verifying output.
.PARAMETER Profile
    The environment profile to use. Defaults to 'local'.
.PARAMETER Quick
    If specified, runs only fast/marked tests.
#>
[CmdletBinding()]
param(
    [string]$Profile = 'local',
    [switch]$Quick
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "=== TraceAI Smoke Tests ===" -ForegroundColor Cyan
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

# Run unit tests
Write-Host "[1/2] Running unit tests..." -ForegroundColor Yellow
if ($Quick) {
    python -m pytest tests/ -x -q --tb=short -m "not slow"
} else {
    python -m pytest tests/ -x -q --tb=short
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Unit tests failed." -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] Unit tests passed." -ForegroundColor Green
Write-Host ""

# Minimal inference test
Write-Host "[2/2] Running minimal inference test..." -ForegroundColor Yellow

$InferenceScript = @"
import sys
from pathlib import Path
model_dir = Path(r'$ProjectRoot') / 'workspace' / 'models' / 'gpt2'
if not model_dir.exists():
    print('  [WARN] Model not found, skipping inference test.')
    sys.exit(0)
from transformers import GPT2LMHeadModel, GPT2Tokenizer
print('  Loading tokenizer...')
tokenizer = GPT2Tokenizer.from_pretrained(str(model_dir))
print('  Loading model...')
model = GPT2LMHeadModel.from_pretrained(str(model_dir))
print('  Generating response...')
inputs = tokenizer.encode('Hello, world', return_tensors='pt')
outputs = model.generate(inputs, max_new_tokens=20, do_sample=False)
text = tokenizer.decode(outputs[0], skip_special_tokens=True)
print(f'  Generated: {text[:80]}...')
if len(text.strip()) == 0:
    print('  [ERROR] Empty generation output')
    sys.exit(1)
print('  [OK] Inference test passed.')
"@

python -c $InferenceScript
if ($LASTEXITCODE -ne 0) {
    Write-Host "[FAIL] Inference test failed." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[OK] All smoke tests passed." -ForegroundColor Green
exit 0
