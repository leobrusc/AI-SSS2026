<#
.SYNOPSIS
    Download the GPT-2 model for local inference.
.DESCRIPTION
    Downloads the GPT-2 model to workspace/models using the transformers library.
    Records model.lock.json with file hashes for integrity verification.
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

Write-Host "=== Download GPT-2 Model ===" -ForegroundColor Cyan
Write-Host "Profile: $Profile"
Write-Host ""

# Activate virtual environment
$VenvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $VenvActivate)) {
    Write-Host "[ERROR] Virtual environment not found at .venv\" -ForegroundColor Red
    Write-Host "Create one with: python -m venv .venv"
    exit 1
}
Write-Host "[1/3] Activating virtual environment..." -ForegroundColor Yellow
& $VenvActivate

# Create models directory
$ModelsDir = Join-Path $ProjectRoot "workspace\models"
if (-not (Test-Path $ModelsDir)) {
    New-Item -ItemType Directory -Path $ModelsDir -Force | Out-Null
}

# Download model using transformers
Write-Host "[2/3] Downloading GPT-2 model..." -ForegroundColor Yellow

$DownloadScript = @"
import json, hashlib, os, datetime
from pathlib import Path
from transformers import GPT2LMHeadModel, GPT2Tokenizer

model_dir = os.path.join(r'$ModelsDir', 'gpt2')
print('  Downloading tokenizer...')
tokenizer = GPT2Tokenizer.from_pretrained('gpt2')
tokenizer.save_pretrained(model_dir)
print('  Downloading model weights...')
model = GPT2LMHeadModel.from_pretrained('gpt2')
model.save_pretrained(model_dir)
print('  Computing file hashes...')
model_path = Path(model_dir)
file_hashes = {}
for f in sorted(model_path.rglob('*')):
    if f.is_file():
        sha256 = hashlib.sha256(f.read_bytes()).hexdigest()
        rel = str(f.relative_to(model_path)).replace('\\', '/')
        file_hashes[rel] = sha256
lock = {
    'model_name': 'gpt2',
    'source': 'huggingface/gpt2',
    'downloaded_at': datetime.datetime.now().isoformat(),
    'profile': '$Profile',
    'files': file_hashes
}
lock_path = os.path.join(r'$ModelsDir', 'model.lock.json')
with open(lock_path, 'w', encoding='utf-8') as f:
    json.dump(lock, f, indent=2)
print(f'  Lock file: {lock_path}')
print(f'  Total files: {len(file_hashes)}')
"@

python -c $DownloadScript
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to download model" -ForegroundColor Red
    exit 1
}

Write-Host "[3/3] Verifying download..." -ForegroundColor Yellow
$LockFile = Join-Path $ModelsDir "model.lock.json"
if (Test-Path $LockFile) {
    Write-Host "  Lock file verified: $LockFile" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "[OK] GPT-2 model downloaded successfully." -ForegroundColor Green
} else {
    Write-Host "[ERROR] Lock file not created" -ForegroundColor Red
    exit 1
}

exit 0
