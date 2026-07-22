# TraceAI Windows Setup Guide

## Overview

TraceAI is developed and tested primarily on Windows 11. This guide covers the complete setup process for Windows environments, including Python installation, virtual environment creation, GPU configuration, and resolution of common Windows-specific issues.

---

## Prerequisites

- Windows 10 (build 1903+) or Windows 11
- 16 GB RAM minimum (32 GB recommended)
- 10 GB free disk space (model download + dependencies)
- NVIDIA GPU with 4+ GB VRAM (optional, CPU fallback available)
- PowerShell 5.1+ (included with Windows) or PowerShell 7+

---

## Python 3.11 Installation

### Recommended: python.org Installer

1. Download Python 3.11.x from https://www.python.org/downloads/
   - Use the **Windows installer (64-bit)** — not the embeddable package
   - Recommended: Python 3.11.9 (latest 3.11 patch)

2. During installation:
   - ✅ Check "Add python.exe to PATH"
   - ✅ Select "Customize installation"
   - ✅ Check "pip", "tcl/tk", "py launcher"
   - ✅ Check "Add Python to environment variables"
   - ⚠️ Select "Install for all users" if you want a system-wide install
   - Set install path to a short path (e.g., `C:\Python311`) to avoid path length issues

3. Verify installation:
   ```powershell
   python --version
   # Expected: Python 3.11.x
   
   pip --version
   # Expected: pip 24.x from ...
   ```

### Alternative: Microsoft Store

The Microsoft Store version works but has known limitations:
- PATH management can conflict with python.org installs
- Some packages that compile native extensions may have issues
- AppExecution aliases can shadow the real Python binary

To disable aliases: Settings → Apps → App execution aliases → disable "python.exe" and "python3.exe" entries from "App Installer".

### Alternative: winget

```powershell
winget install Python.Python.3.11
```

---

## PowerShell Execution Policy

TraceAI scripts require PowerShell script execution. We recommend setting the policy **for the current process only** to avoid system-wide security changes:

```powershell
# Set for current process only (recommended — no system-wide change)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

This must be run at the start of each new PowerShell session, or you can add it to your PowerShell profile.

### Why Process Scope?

- **Process**: Only affects the current terminal session. Safest option.
- **CurrentUser**: Persists across sessions for your user account.
- **LocalMachine**: Affects all users. Requires admin. NOT recommended.

### Verify Policy

```powershell
Get-ExecutionPolicy -List
# Process should show RemoteSigned or Unrestricted
```

### If Scripts Still Won't Run

If you downloaded scripts from the internet, Windows may mark them as blocked:

```powershell
# Unblock all scripts in the project
Get-ChildItem -Path . -Recurse -Filter "*.ps1" | Unblock-File
```

---

## Virtual Environment Creation

### Create the venv

```powershell
# Navigate to project root
cd C:\Users\leolima\Documents\traceai-ladc2026

# Create virtual environment
python -m venv .venv

# Activate
.\.venv\Scripts\Activate.ps1
```

### Verify Activation

```powershell
# Should show the .venv path
python -c "import sys; print(sys.prefix)"
# Expected: C:\Users\leolima\Documents\traceai-ladc2026\.venv

# Confirm pip is from venv
pip --version
# Should reference .venv path
```

### Install Dependencies

```powershell
# Upgrade pip first
python -m pip install --upgrade pip

# Install from lock file (if hashes are present)
pip install -r requirements.lock --require-hashes

# Or during development (without hash verification)
pip install -r requirements.in
pip install -r requirements-dev.in

# Install the project in editable mode
pip install -e .
```

### Deactivation

```powershell
deactivate
```

---

## CUDA / GPU Detection

### Check NVIDIA Driver

```powershell
# Check if nvidia-smi is available
nvidia-smi
```

Expected output shows GPU name, driver version, and CUDA version. If this fails, install the latest NVIDIA driver from https://www.nvidia.com/drivers.

### Check PyTorch CUDA Support

```powershell
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}')"
```

### CUDA Version Compatibility

| PyTorch Version | Supported CUDA | Notes |
|----------------|----------------|-------|
| 2.2.x          | 11.8, 12.1     | Default pip install uses CUDA 12.1 |
| 2.1.x          | 11.8, 12.1     | |
| 2.0.x          | 11.7, 11.8     | |

If PyTorch doesn't detect CUDA despite having an NVIDIA GPU:

1. Verify driver version supports your CUDA toolkit:
   ```powershell
   nvidia-smi  # Shows "CUDA Version: 12.x" in top right
   ```

2. Install CUDA-enabled PyTorch explicitly:
   ```powershell
   pip install torch --index-url https://download.pytorch.org/whl/cu121
   ```

3. Check for version mismatch:
   ```powershell
   python -c "import torch; print(torch.version.cuda)"
   ```

### CPU Fallback

TraceAI automatically falls back to CPU if no GPU is detected. The `device: auto` setting in profile configuration handles this:

```python
# In settings/profiles
device: auto  # Detects GPU, falls back to CPU
```

Performance will be significantly lower on CPU (approximately 10-50x slower for inference), but all experiments remain functionally valid.

### GPU Memory Monitoring

TraceAI enforces GPU memory safety limits (default 80%):

```powershell
# Check GPU memory usage
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits
```

If GPU memory is exhausted, reduce `max_concurrency` in the profile or use `--quick` mode for campaigns.

---

## Path Length Issues

Windows has a default maximum path length of 260 characters. Deep dependency trees and long model file names can exceed this.

### Enable Long Paths (Recommended)

**Option 1: Registry (requires admin)**
```powershell
# Run as Administrator
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

**Option 2: Group Policy (requires admin)**
1. Run `gpedit.msc`
2. Navigate to: Computer Configuration → Administrative Templates → System → Filesystem
3. Enable "Enable Win32 long paths"

**Option 3: Python manifest (already handled)**

Python 3.6+ includes a manifest enabling long paths. Verify:
```powershell
python -c "import sys; print(sys.executable)"
# If this path itself is long, Python has long-path support
```

### Workaround: Short Project Path

If you cannot enable long paths system-wide, place the project in a short path:

```powershell
# Instead of deeply nested user directories
# BAD:  C:\Users\username\OneDrive\Documents\Research\2026\LADC\traceai-ladc2026
# GOOD: C:\dev\traceai
```

### Symptoms of Path Length Issues

- `FileNotFoundError` when installing packages with deep dependency trees
- `OSError: [Errno 22]` during model download
- `shutil.copy` failures during fault injection workspace setup

---

## Common Errors and Solutions

### Error: `Scripts\Activate.ps1 cannot be loaded because running scripts is disabled`

**Cause**: PowerShell execution policy blocks script execution.

**Solution**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

---

### Error: `'python' is not recognized as an internal or external command`

**Cause**: Python not in PATH, or Microsoft Store alias intercepting.

**Solution**:
1. Verify Python installation: `where.exe python`
2. If using Microsoft Store Python, disable App Execution Aliases
3. Add Python to PATH manually:
   ```powershell
   $env:PATH = "C:\Python311;C:\Python311\Scripts;$env:PATH"
   ```

---

### Error: `torch.cuda.is_available() returns False`

**Cause**: CPU-only PyTorch installed, or CUDA driver mismatch.

**Solution**:
```powershell
# Reinstall with CUDA support
pip uninstall torch
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

---

### Error: `OSError: [WinError 1314] A required privilege is not held by the client`

**Cause**: Attempting to create symlinks without developer mode or admin rights.

**Solution**:
1. Enable Developer Mode: Settings → For Developers → Developer Mode → On
2. Or run PowerShell as Administrator (not recommended for general use)

---

### Error: `PermissionError: [Errno 13] Permission denied` on model files

**Cause**: Another process has the model files open (e.g., antivirus scanning, another Python process).

**Solution**:
1. Close other Python processes: `Get-Process python | Stop-Process`
2. Exclude `workspace/models/` from Windows Defender real-time scanning:
   ```powershell
   # Run as Administrator
   Add-MpPreference -ExclusionPath "C:\Users\leolima\Documents\traceai-ladc2026\workspace"
   ```

---

### Error: `UnicodeDecodeError` when reading files

**Cause**: Windows default encoding is not UTF-8.

**Solution**: TraceAI explicitly uses `encoding="utf-8"` in all file operations. If you encounter this in a third-party tool, set:
```powershell
$env:PYTHONUTF8 = "1"
```

Or add to your PowerShell profile:
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
```

---

### Error: `pip install` fails with SSL certificate errors

**Cause**: Corporate proxy, antivirus SSL inspection, or outdated certificates.

**Solution**:
```powershell
# Temporary: trust PyPI
pip install --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.lock

# Or set permanently
pip config set global.trusted-host "pypi.org pypi.python.org files.pythonhosted.org"
```

---

### Error: `CUDA out of memory` during inference

**Cause**: GPU VRAM insufficient for model + inference batch.

**Solution**:
1. Reduce `max_concurrency` in profile config
2. Use `--quick` mode for campaigns (fewer concurrent requests)
3. Ensure no other GPU-intensive processes are running:
   ```powershell
   nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv
   ```
4. GPT-2 (124M parameters) requires ~500MB VRAM. If your GPU has less than 2GB free, close other applications.

---

### Error: Port 8000 already in use

**Cause**: Another process (or a previous TraceAI instance) occupies the port.

**Solution**:
```powershell
# Find what's using port 8000
netstat -ano | findstr ":8000"

# Kill the process (replace PID)
Stop-Process -Id <PID> -Force

# Or use a different port
traceai serve --port 8001
```

---

### Error: `ModuleNotFoundError: No module named 'traceai'`

**Cause**: Package not installed in editable mode, or venv not activated.

**Solution**:
```powershell
# Ensure venv is active
.\.venv\Scripts\Activate.ps1

# Install in editable mode
pip install -e .
```

---

## Quick Start Summary

```powershell
# 1. Set execution policy (each session)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# 2. Navigate to project
cd C:\Users\leolima\Documents\traceai-ladc2026

# 3. Create and activate venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 4. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.in
pip install -r requirements-dev.in
pip install -e .

# 5. Run bootstrap
.\scripts\bootstrap.ps1

# 6. Verify environment
traceai doctor --profile local

# 7. Run smoke test
.\scripts\smoke.ps1
```
