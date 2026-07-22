<#
.SYNOPSIS
    Remove generated/ directory contents with confirmation.
.DESCRIPTION
    Removes all contents of the generated/ directory after prompting for confirmation.
.PARAMETER Profile
    The environment profile to use. Defaults to 'local'.
.PARAMETER Force
    If specified, skip confirmation prompt.
#>
[CmdletBinding()]
param(
    [string]$Profile = 'local',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "=== Clean Generated Artifacts ===" -ForegroundColor Cyan
Write-Host "Profile: $Profile"
Write-Host ""

$GeneratedDir = Join-Path $ProjectRoot "generated"

if (-not (Test-Path $GeneratedDir)) {
    Write-Host "[OK] Nothing to clean - generated/ does not exist." -ForegroundColor Green
    exit 0
}

# Show what will be deleted
$Items = Get-ChildItem -Path $GeneratedDir -Recurse
$FileCount = ($Items | Where-Object { -not $_.PSIsContainer }).Count
$DirCount = ($Items | Where-Object { $_.PSIsContainer }).Count

Write-Host "Contents of generated/:" -ForegroundColor Yellow
Write-Host "  Files:       $FileCount"
Write-Host "  Directories: $DirCount"
Write-Host ""

# Confirmation
if (-not $Force) {
    $Response = Read-Host "Are you sure you want to delete all contents of generated/? (y/N)"
    if ($Response -notin @('y', 'Y', 'yes', 'Yes', 'YES')) {
        Write-Host "[CANCELLED] No files were deleted." -ForegroundColor Yellow
        exit 0
    }
}

# Remove contents
Write-Host "[*] Removing generated/ contents..." -ForegroundColor Yellow
Get-ChildItem -Path $GeneratedDir -Recurse | Remove-Item -Recurse -Force
Write-Host ""
Write-Host "[OK] Cleaned $FileCount file(s) and $DirCount directory(ies) from generated/." -ForegroundColor Green
exit 0
