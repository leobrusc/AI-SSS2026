# GPU Runbook — TraceAI LADC 2026

**Generated:** 2026-07-23T18:27:07.413442+00:00
**Recommended Device:** `cpu`
**GPU Ready:** ✗ No

## Preflight Results

| Check | Status | Message |
|-------|--------|---------|
| torch_installed | ✓ | PyTorch 2.13.0+cpu installed |
| nvidia_driver | ⚠ | nvidia-smi not found in PATH |
| cuda_available | ⚠ | CUDA not available (torch.cuda.is_available() = False) |
| gpu_name_matches | ✓ | N/A (CPU mode, profile expects: NVIDIA L4) |
| cuda_torch_compat | ✓ | N/A (CPU mode — no compatibility issue) |
| vram_sufficient | ✓ | N/A (CPU mode) |
| nvml_available | ⚠ | pynvml not installed (install with: pip install pynvml) |
| no_competing_gpu_processes | ✓ | nvidia-smi not available (skipped on this platform) |
| device_config | ✓ | TRACEAI_DEVICE='auto' (valid) |
| model_loadable | ✓ | Model config loaded: sshleifer/tiny-gpt2 (gpt2) |

## Device Selection Logic

TraceAI uses automatic device detection (`device: auto` in config):

```python
# In src/traceai/service/inference.py
if self._device_config == 'auto':
    self._device_resolved = 'cuda' if torch.cuda.is_available() else 'cpu'
```

Override via environment: `$env:TRACEAI_DEVICE = 'cuda'` or `'cpu'`

## Transitioning to GPU

### Prerequisites

1. NVIDIA GPU with Compute Capability >= 3.7
2. NVIDIA driver installed (verify with `nvidia-smi`)
3. PyTorch with CUDA support matching your driver

### Install PyTorch with CUDA (if not already)

```powershell
# Detect installed CUDA version from driver
nvidia-smi  # Look for 'CUDA Version: X.Y'

# Select correct wheel from https://pytorch.org/get-started/locally/
pip install torch --index-url https://download.pytorch.org/whl/<cuXXX>

# Verify
python -c "import torch; print(torch.cuda.is_available())"
```

**Do NOT hard-code a specific CUDA wheel version.** Always match
your installed NVIDIA driver's CUDA capability.

### Validation

```powershell
# Run preflight checks
python scripts/phase5_gpu_runbook.py

# Or run the doctor command
.\tasks.ps1 doctor -Profile local
```

### Expected Performance Difference

| Metric | CPU (baseline) | GPU (expected) |
|--------|---------------|----------------|
| Model load time | ~90s | ~15s |
| C0 P50 (50 tokens) | ~1000ms | ~100ms |
| C1 P50 (20 tokens) | ~350ms | ~50ms |
| Throughput | ~20 tok/s | ~200 tok/s |

## Troubleshooting

### 'No kernel image available'
Your PyTorch CUDA version doesn't match your GPU. Reinstall PyTorch
with the correct CUDA version for your driver.

### Out of Memory
GPT-2 (124M params) needs ~500MB VRAM. If VRAM < 2GB free,
close other GPU applications first.

### CPU fallback
If GPU is unavailable, TraceAI automatically falls back to CPU.
All experiments produce valid results on either device.
GPU experiments simply run faster.

## Current Warnings

- ⚠ nvidia-smi not found in PATH
- ⚠ CUDA not available (torch.cuda.is_available() = False)
- ⚠ pynvml not installed (install with: pip install pynvml)