<#
.SYNOPSIS
    Export campaign results as a portable bundle.
#>
param([string]$OutputPath = "")

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path "$root\pyproject.toml")) { $root = Get-Location }
Set-Location $root

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
if (-not $OutputPath) { $OutputPath = "campaign_bundle_$timestamp.tar.gz" }

$bundleDir = "workspace\bundle_$timestamp"
New-Item -ItemType Directory -Path $bundleDir -Force | Out-Null

# Copy results and generated
if (Test-Path results) { Copy-Item -Recurse results "$bundleDir\results" }
if (Test-Path generated) { Copy-Item -Recurse generated "$bundleDir\generated" }
Copy-Item model.lock.json "$bundleDir\" -ErrorAction SilentlyContinue
Copy-Item tools.lock.json "$bundleDir\" -ErrorAction SilentlyContinue

# Create archive
Compress-Archive -Path "$bundleDir\*" -DestinationPath "$OutputPath.zip" -Force
Write-Host "Bundle created: $OutputPath.zip"

# Cleanup
Remove-Item $bundleDir -Recurse -Force
