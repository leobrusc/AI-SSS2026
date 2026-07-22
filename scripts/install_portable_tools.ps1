<#
.SYNOPSIS
    Install portable security tools for TraceAI.
.DESCRIPTION
    Downloads Syft, Grype, Trivy, and Cosign to .tools\bin
    without admin privileges. Verifies checksums when available.
.PARAMETER Force
    Force reinstall even if tools already exist.
#>
param([switch]$Force)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path "$ProjectRoot\pyproject.toml")) {
    $ProjectRoot = Get-Location
}
Set-Location $ProjectRoot

$ToolsDir = Join-Path $ProjectRoot ".tools"
$BinDir = Join-Path $ToolsDir "bin"
$TmpDir = Join-Path $ToolsDir "tmp"
New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
New-Item -ItemType Directory -Path $TmpDir -Force | Out-Null

# Add to PATH for this process
$env:PATH = "$BinDir;$env:PATH"

$report = @{
    timestamp = (Get-Date -Format "o")
    tools = @{}
    errors = @()
}

# Tool definitions with pinned versions
$tools = @(
    @{
        name = "syft"
        version = "1.18.1"
        url = "https://github.com/anchore/syft/releases/download/v1.18.1/syft_1.18.1_windows_amd64.zip"
        exe = "syft.exe"
        checksumUrl = "https://github.com/anchore/syft/releases/download/v1.18.1/syft_1.18.1_checksums.txt"
        archiveFile = "syft_1.18.1_windows_amd64.zip"
    },
    @{
        name = "grype"
        version = "0.86.1"
        url = "https://github.com/anchore/grype/releases/download/v0.86.1/grype_0.86.1_windows_amd64.zip"
        exe = "grype.exe"
        checksumUrl = "https://github.com/anchore/grype/releases/download/v0.86.1/grype_0.86.1_checksums.txt"
        archiveFile = "grype_0.86.1_windows_amd64.zip"
    },
    @{
        name = "trivy"
        version = "0.58.2"
        url = "https://github.com/aquasecurity/trivy/releases/download/v0.58.2/trivy_0.58.2_Windows-64bit.zip"
        exe = "trivy.exe"
        checksumUrl = "https://github.com/aquasecurity/trivy/releases/download/v0.58.2/trivy_0.58.2_checksums.txt"
        archiveFile = "trivy_0.58.2_Windows-64bit.zip"
    },
    @{
        name = "cosign"
        version = "2.4.1"
        url = "https://github.com/sigstore/cosign/releases/download/v2.4.1/cosign-windows-amd64.exe"
        exe = "cosign.exe"
        checksumUrl = ""
        archiveFile = "cosign-windows-amd64.exe"
        directExe = $true
    }
)

foreach ($tool in $tools) {
    $exePath = Join-Path $BinDir $tool.exe
    $toolName = $tool.name

    Write-Host "`n[$toolName] version=$($tool.version)"

    if ((Test-Path $exePath) -and -not $Force) {
        Write-Host "  Already installed at $exePath"
        $report.tools[$toolName] = @{
            version = $tool.version
            status = "already_installed"
            path = $exePath
            url = $tool.url
        }
        continue
    }

    $archivePath = Join-Path $TmpDir $tool.archiveFile
    $downloaded = $false

    # Download
    try {
        Write-Host "  Downloading from $($tool.url)..."
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $wc = New-Object System.Net.WebClient
        $wc.DownloadFile($tool.url, $archivePath)
        $downloaded = $true
        Write-Host "  Downloaded: $archivePath"
    } catch {
        Write-Host "  [WARN] Download failed: $_" -ForegroundColor Yellow
        $report.tools[$toolName] = @{
            version = $tool.version
            status = "download_failed"
            error = $_.ToString()
            url = $tool.url
        }
        $report.errors += "Failed to download $toolName : $_"
        continue
    }

    # Compute SHA-256
    $sha256 = (Get-FileHash -Path $archivePath -Algorithm SHA256).Hash.ToLower()
    Write-Host "  SHA-256: $sha256"

    # Verify checksum if available
    $checksumVerified = "not_available"
    if ($tool.checksumUrl -and $downloaded) {
        try {
            $checksumFile = Join-Path $TmpDir "$($toolName)_checksums.txt"
            $wc.DownloadFile($tool.checksumUrl, $checksumFile)
            $checksumContent = Get-Content $checksumFile -Raw
            if ($checksumContent -match $sha256) {
                $checksumVerified = "verified"
                Write-Host "  Checksum VERIFIED" -ForegroundColor Green
            } else {
                # Check if our file's name appears with a different hash
                $expectedLine = ($checksumContent -split "`n") | Where-Object { $_ -match [regex]::Escape($tool.archiveFile) }
                if ($expectedLine) {
                    $expectedHash = ($expectedLine -split "\s+")[0].ToLower()
                    if ($expectedHash -eq $sha256) {
                        $checksumVerified = "verified"
                        Write-Host "  Checksum VERIFIED" -ForegroundColor Green
                    } else {
                        $checksumVerified = "FAILED"
                        Write-Host "  [ERROR] Checksum MISMATCH! Expected: $expectedHash" -ForegroundColor Red
                        $report.errors += "$toolName checksum mismatch"
                        continue
                    }
                } else {
                    $checksumVerified = "file_not_in_checksums"
                    Write-Host "  Checksum file downloaded but archive not listed" -ForegroundColor Yellow
                }
            }
        } catch {
            $checksumVerified = "checksum_download_failed"
            Write-Host "  Could not download checksum file: $_" -ForegroundColor Yellow
        }
    }

    # Extract or copy
    try {
        if ($tool.directExe) {
            Copy-Item $archivePath $exePath -Force
        } else {
            Expand-Archive -Path $archivePath -DestinationPath $TmpDir -Force
            $extractedExe = Get-ChildItem -Path $TmpDir -Recurse -Filter $tool.exe | Select-Object -First 1
            if ($extractedExe) {
                Copy-Item $extractedExe.FullName $exePath -Force
            } else {
                throw "Executable $($tool.exe) not found in archive"
            }
        }
        Write-Host "  Installed: $exePath" -ForegroundColor Green
    } catch {
        Write-Host "  [ERROR] Extraction failed: $_" -ForegroundColor Red
        $report.tools[$toolName] = @{
            version = $tool.version
            status = "extraction_failed"
            error = $_.ToString()
        }
        continue
    }

    $report.tools[$toolName] = @{
        version = $tool.version
        status = "installed"
        path = $exePath
        url = $tool.url
        sha256 = $sha256
        checksum_verified = $checksumVerified
    }
}

# Clean tmp
Remove-Item $TmpDir -Recurse -Force -ErrorAction SilentlyContinue

# Verify installations
Write-Host "`n--- Verification ---"
foreach ($tool in $tools) {
    $exePath = Join-Path $BinDir $tool.exe
    if (Test-Path $exePath) {
        try {
            $ver = & $exePath version 2>&1 | Select-Object -First 1
            Write-Host "  $($tool.name): $ver" -ForegroundColor Green
            $report.tools[$tool.name]["detected_version"] = $ver
        } catch {
            Write-Host "  $($tool.name): installed but version check failed" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  $($tool.name): NOT INSTALLED" -ForegroundColor Red
    }
}

# Save reports
$genDir = Join-Path $ProjectRoot "generated" "tools"
New-Item -ItemType Directory -Path $genDir -Force | Out-Null

$report | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $genDir "tool_versions.json") -Encoding UTF8

# tool_install_report.md
$mdLines = @(
    "# Tool Installation Report"
    ""
    "Generated: $($report.timestamp)"
    ""
    "| Tool | Version | Status | Checksum |"
    "|------|---------|--------|----------|"
)
foreach ($tool in $tools) {
    $info = $report.tools[$tool.name]
    if ($info) {
        $mdLines += "| $($tool.name) | $($info.version) | $($info.status) | $($info.checksum_verified) |"
    }
}
if ($report.errors.Count -gt 0) {
    $mdLines += ""
    $mdLines += "## Errors"
    foreach ($e in $report.errors) { $mdLines += "- $e" }
}
$mdLines -join "`n" | Set-Content (Join-Path $genDir "tool_install_report.md") -Encoding UTF8

Write-Host "`nTool installation complete. Reports in: $genDir"
