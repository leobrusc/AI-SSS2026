<#
.SYNOPSIS
    TraceAI task runner for LADC 2026 experiments.

.DESCRIPTION
    Canonical command interface for all TraceAI operations.
    Activates .venv automatically, validates tasks, and manages campaigns.

.PARAMETER Task
    The task to execute: doctor, bootstrap, smoke, security-campaign,
    availability-campaign, analyze, publication-artifacts, all

.PARAMETER Profile
    Execution profile: local, container, industrial (default: local)

.PARAMETER Quick
    Run reduced campaigns (3 trials, 20 requests) instead of full (30 trials, 200 requests)

.EXAMPLE
    .\tasks.ps1 doctor -Profile local
    .\tasks.ps1 bootstrap -Profile local
    .\tasks.ps1 smoke -Profile local
    .\tasks.ps1 security-campaign -Profile local -Quick
    .\tasks.ps1 all -Profile local
#>

param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("doctor", "bootstrap", "smoke", "security-campaign",
                 "availability-campaign", "analyze", "publication-artifacts", "all",
                 "audit", "install-tools", "rq1-campaign", "rq3-campaign",
                 "validate-publication", "publication-readiness")]
    [string]$Task,

    [ValidateSet("local", "container", "industrial")]
    [string]$Profile = "local",

    [switch]$Quick,

    [string]$ResearchQuestion = "",

    [switch]$Force
)

$ErrorActionPreference = "Stop"
$script:StartTime = Get-Date
$script:ProjectRoot = $PSScriptRoot

# Ensure we're in the project root
if (-not (Test-Path "$script:ProjectRoot\pyproject.toml")) {
    # If running from project root directly
    if (Test-Path ".\pyproject.toml") {
        $script:ProjectRoot = (Get-Location).Path
    } else {
        Write-Error "Cannot find project root. Run from the traceai-ladc2026 directory."
        exit 1
    }
}

Set-Location $script:ProjectRoot

# --- Logging ---
$script:LogDir = Join-Path $script:ProjectRoot "workspace"
if (-not (Test-Path $script:LogDir)) { New-Item -ItemType Directory -Path $script:LogDir -Force | Out-Null }
$script:LogFile = Join-Path $script:LogDir "tasks_$(Get-Date -Format 'yyyyMMdd-HHmmss').log"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $script:LogFile -Value $entry -Encoding UTF8
    switch ($Level) {
        "ERROR" { Write-Host $entry -ForegroundColor Red }
        "WARN"  { Write-Host $entry -ForegroundColor Yellow }
        "OK"    { Write-Host $entry -ForegroundColor Green }
        default { Write-Host $entry }
    }
}

# --- Virtual Environment ---
function Activate-Venv {
    $venvActivate = Join-Path $script:ProjectRoot ".venv\Scripts\Activate.ps1"
    if (-not (Test-Path $venvActivate)) {
        Write-Log "Virtual environment not found at .venv\Scripts\Activate.ps1" "ERROR"
        Write-Log "Run: python -m venv .venv" "ERROR"
        exit 1
    }
    & $venvActivate
    Write-Log "Virtual environment activated"
}

# --- Task Dispatch ---
function Invoke-Task {
    param([string]$TaskName)

    Write-Log "=" * 60
    Write-Log "Task: $TaskName | Profile: $Profile | Quick: $Quick"
    Write-Log "=" * 60

    switch ($TaskName) {
        "audit" {
            Activate-Venv
            $cmd = "python -m traceai audit --profile $Profile --output generated"
            Write-Log "Executing: $cmd"
            Invoke-Expression $cmd
            Write-Log "Audit completed" "OK"
        }
        "install-tools" {
            $scriptPath = Join-Path $script:ProjectRoot "scripts\install_portable_tools.ps1"
            Write-Log "Executing: $scriptPath -Profile $Profile"
            if ($Force) {
                & $scriptPath -Force
            } else {
                & $scriptPath
            }
            Write-Log "Tool installation completed" "OK"
        }
        "rq1-campaign" {
            Activate-Venv
            $quickFlag = if ($Quick) { "--quick" } else { "" }
            $cmd = "python -m traceai rq1-campaign --profile $Profile $quickFlag"
            Write-Log "Executing: $cmd"
            Invoke-Expression $cmd
            if ($LASTEXITCODE -ne 0) {
                Write-Log "RQ1 campaign failed" "ERROR"
                exit 1
            }
            Write-Log "RQ1 campaign completed" "OK"
        }
        "rq3-campaign" {
            Activate-Venv
            $quickFlag = if ($Quick) { "--quick" } else { "" }
            $cmd = "python -m traceai rq3-campaign --profile $Profile $quickFlag"
            Write-Log "Executing: $cmd"
            Invoke-Expression $cmd
            if ($LASTEXITCODE -ne 0) {
                Write-Log "RQ3 campaign failed" "ERROR"
                exit 1
            }
            Write-Log "RQ3 campaign completed" "OK"
        }
        "validate-publication" {
            Activate-Venv
            if (-not $ResearchQuestion) {
                Write-Log "ResearchQuestion parameter required (RQ1, RQ2, RQ3, RQ4)" "ERROR"
                exit 1
            }
            $cmd = "python -m traceai validate-publication --profile $Profile --research-question $ResearchQuestion"
            Write-Log "Executing: $cmd"
            Invoke-Expression $cmd
            Write-Log "Publication validation for $ResearchQuestion completed" "OK"
        }
        "publication-readiness" {
            Activate-Venv
            $cmd = "python -m traceai publication-readiness --profile $Profile --output generated"
            Write-Log "Executing: $cmd"
            Invoke-Expression $cmd
            Write-Log "Publication readiness report completed" "OK"
        }
        "doctor" {
            Activate-Venv
            $cmd = "python -m traceai doctor --profile $Profile --output generated"
            Write-Log "Executing: $cmd"
            Invoke-Expression $cmd
            if ($LASTEXITCODE -ne 0) {
                Write-Log "Doctor reported issues (exit code: $LASTEXITCODE)" "WARN"
            } else {
                Write-Log "Doctor completed successfully" "OK"
            }
        }
        "bootstrap" {
            $scriptPath = Join-Path $script:ProjectRoot "scripts\bootstrap.ps1"
            Write-Log "Executing: $scriptPath -Profile $Profile"
            & $scriptPath -Profile $Profile
            Write-Log "Bootstrap completed" "OK"
        }
        "smoke" {
            Activate-Venv
            $scriptPath = Join-Path $script:ProjectRoot "scripts\smoke.ps1"
            Write-Log "Executing: $scriptPath -Profile $Profile"
            & $scriptPath -Profile $Profile
            if ($LASTEXITCODE -ne 0) {
                Write-Log "Smoke tests FAILED" "ERROR"
                exit 1
            }
            Write-Log "Smoke tests passed" "OK"
        }
        "security-campaign" {
            Activate-Venv
            $quickFlag = if ($Quick) { "--quick" } else { "" }
            $cmd = "python -m traceai campaign security --profile $Profile $quickFlag"
            Write-Log "Executing: $cmd"
            Invoke-Expression $cmd
            if ($LASTEXITCODE -ne 0) {
                Write-Log "Security campaign failed" "ERROR"
                exit 1
            }
            Write-Log "Security campaign completed" "OK"
        }
        "availability-campaign" {
            Activate-Venv
            $quickFlag = if ($Quick) { "--quick" } else { "" }
            $cmd = "python -m traceai campaign availability --profile $Profile $quickFlag"
            Write-Log "Executing: $cmd"
            Invoke-Expression $cmd
            if ($LASTEXITCODE -ne 0) {
                Write-Log "Availability campaign failed" "ERROR"
                exit 1
            }
            Write-Log "Availability campaign completed" "OK"
        }
        "analyze" {
            Activate-Venv
            $cmd = "python -m traceai analyze --profile $Profile --input results --output generated"
            Write-Log "Executing: $cmd"
            Invoke-Expression $cmd
            Write-Log "Analysis completed" "OK"
        }
        "publication-artifacts" {
            Activate-Venv
            $scriptPath = Join-Path $script:ProjectRoot "scripts\publication_artifacts.ps1"
            Write-Log "Executing: $scriptPath -Profile $Profile"
            & $scriptPath -Profile $Profile
            Write-Log "Publication artifacts generated" "OK"
        }
        "all" {
            Write-Log "Running full pipeline (Profile: $Profile, Quick: $Quick)"
            $tasks = @("doctor", "bootstrap", "smoke")
            if ($Quick) {
                $tasks += @("security-campaign", "availability-campaign")
            } else {
                $tasks += @("security-campaign", "availability-campaign")
            }
            $tasks += @("analyze", "publication-artifacts")

            foreach ($t in $tasks) {
                Invoke-Task -TaskName $t
            }
            Write-Log "Full pipeline completed" "OK"
        }
    }
}

# --- Main ---
Write-Log "TraceAI Task Runner started"
Write-Log "Project root: $script:ProjectRoot"
Write-Log "Log file: $script:LogFile"

try {
    Invoke-Task -TaskName $Task
    $elapsed = (Get-Date) - $script:StartTime
    Write-Log "Task '$Task' completed in $($elapsed.TotalSeconds.ToString('F1'))s" "OK"
    Write-Log "Output directory: $(Join-Path $script:ProjectRoot 'generated')"
    exit 0
} catch {
    Write-Log "Task '$Task' FAILED: $_" "ERROR"
    Write-Log $_.ScriptStackTrace "ERROR"
    exit 1
}
