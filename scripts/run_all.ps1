<#
.SYNOPSIS
    Run the full TraceAI pipeline.
.DESCRIPTION
    Orchestrates the full pipeline: doctor, bootstrap, smoke tests, campaigns,
    analysis, and publication artifacts.
.PARAMETER Profile
    The environment profile to use. Defaults to 'local'.
.PARAMETER Quick
    If specified, passes -Quick to applicable steps.
#>
[CmdletBinding()]
param(
    [string]$Profile = 'local',
    [switch]$Quick
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ScriptsDir = $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "   TraceAI Full Pipeline" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Profile: $Profile"
if ($Quick) { Write-Host "Mode: Quick" }
Write-Host ""

$Steps = @(
    @{ Name = "Doctor";              Script = "doctor.ps1";                  UseQuick = $false },
    @{ Name = "Bootstrap";           Script = "bootstrap.ps1";              UseQuick = $false },
    @{ Name = "Smoke Tests";         Script = "smoke.ps1";                  UseQuick = $true  },
    @{ Name = "Security Campaign";   Script = "run_security_campaign.ps1";  UseQuick = $true  },
    @{ Name = "Availability Campaign"; Script = "run_availability_campaign.ps1"; UseQuick = $true },
    @{ Name = "Analyze";             Script = "analyze.ps1";                UseQuick = $false },
    @{ Name = "Publication";         Script = "publication_artifacts.ps1";  UseQuick = $false }
)

$TotalSteps = $Steps.Count
$CurrentStep = 0
$StartTime = Get-Date

foreach ($step in $Steps) {
    $CurrentStep++
    Write-Host ""
    Write-Host "[$CurrentStep/$TotalSteps] $($step.Name)" -ForegroundColor Magenta
    Write-Host ("-" * 40)

    $ScriptPath = Join-Path $ScriptsDir $step.Script
    $Args = @("-Profile", $Profile)
    if ($Quick -and $step.UseQuick) {
        $Args += "-Quick"
    }

    & $ScriptPath @Args
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "[ABORT] Pipeline failed at step: $($step.Name) (exit code: $LASTEXITCODE)" -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

$Duration = (Get-Date) - $StartTime
Write-Host ""
Write-Host "======================================" -ForegroundColor Green
Write-Host "   Pipeline Complete" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Green
Write-Host "Duration: $($Duration.ToString('hh\:mm\:ss'))"
Write-Host "Profile:  $Profile"
exit 0
