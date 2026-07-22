<#
.SYNOPSIS
    Copy generated artifacts to results/public and sanitize.
.DESCRIPTION
    Copies generated artifacts to results/public directory and runs sanitization
    to remove sensitive data before publication.
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

Write-Host "=== TraceAI Publication Artifacts ===" -ForegroundColor Cyan
Write-Host "Profile: $Profile"
Write-Host ""

$GeneratedDir = Join-Path $ProjectRoot "generated"
$PublicDir = Join-Path $ProjectRoot "results\public"

# Verify generated directory exists
if (-not (Test-Path $GeneratedDir)) {
    Write-Host "[ERROR] Generated directory not found: $GeneratedDir" -ForegroundColor Red
    Write-Host "Run the pipeline first to produce artifacts."
    exit 1
}

# Create public output directory
if (-not (Test-Path $PublicDir)) {
    New-Item -ItemType Directory -Path $PublicDir -Force | Out-Null
}

# Copy artifacts
Write-Host "[1/3] Copying artifacts to results/public..." -ForegroundColor Yellow
$Items = Get-ChildItem -Path $GeneratedDir -Recurse
$Count = 0
foreach ($item in $Items) {
    if ($item.PSIsContainer) { continue }
    $RelPath = $item.FullName.Substring($GeneratedDir.Length + 1)
    $DestPath = Join-Path $PublicDir $RelPath
    $DestDir = Split-Path -Parent $DestPath
    if (-not (Test-Path $DestDir)) {
        New-Item -ItemType Directory -Path $DestDir -Force | Out-Null
    }
    Copy-Item -Path $item.FullName -Destination $DestPath -Force
    $Count++
}
Write-Host "  Copied $Count file(s)." -ForegroundColor DarkGray

# Sanitization: remove potential sensitive patterns
Write-Host "[2/3] Sanitizing artifacts..." -ForegroundColor Yellow
$SensitivePatterns = @(
    '(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*\S+',
    '(?i)(aws_access_key_id|aws_secret_access_key)\s*=\s*\S+'
)

$SanitizedCount = 0
$PublicFiles = Get-ChildItem -Path $PublicDir -Recurse -File
foreach ($file in $PublicFiles) {
    $Content = Get-Content -Path $file.FullName -Raw -ErrorAction SilentlyContinue
    if ($null -eq $Content) { continue }
    $Modified = $false
    foreach ($pattern in $SensitivePatterns) {
        if ($Content -match $pattern) {
            $Content = $Content -replace $pattern, '[REDACTED]'
            $Modified = $true
        }
    }
    if ($Modified) {
        Set-Content -Path $file.FullName -Value $Content -Encoding UTF8
        $SanitizedCount++
    }
}
Write-Host "  Sanitized $SanitizedCount file(s)." -ForegroundColor DarkGray

# Generate manifest
Write-Host "[3/3] Generating publication manifest..." -ForegroundColor Yellow
$Manifest = @{
    generated_at = (Get-Date -Format "o")
    profile      = $Profile
    source       = "generated/"
    destination  = "results/public/"
    files_copied = $Count
    files_sanitized = $SanitizedCount
}
$ManifestPath = Join-Path $PublicDir "publication_manifest.json"
$Manifest | ConvertTo-Json -Depth 4 | Set-Content -Path $ManifestPath -Encoding UTF8

Write-Host ""
Write-Host "[OK] Publication artifacts ready at: $PublicDir" -ForegroundColor Green
exit 0
