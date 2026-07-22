# GPU Campaign Runbook — NVIDIA RTX A5000

## Target Environment

- **GPU:** NVIDIA RTX A5000 (24 GB VRAM)
- **OS:** Linux (Ubuntu 22.04 or equivalent)
- **CUDA:** Runtime-detected (do not hard-code version)
- **Python:** 3.11+
- **Model:** openai-community/gpt2 (124M), then optionally larger

## Pre-Requisites

The following must be verified at runtime (not assumed):

```bash
nvidia-smi  # Must succeed
python -c "import torch; assert torch.cuda.is_available()"
python -c "import torch; print(torch.cuda.get_device_name(0))"
```

## 1. Clone or Import Repository

```bash
# Option A: Clone
git clone <repo-url> traceai-ladc2026
cd traceai-ladc2026
git checkout traceai-methodology-v2

# Option B: Import bundle
./scripts/import_campaign_bundle.sh campaign_bundle.tar.gz
cd traceai-ladc2026
```

## 2. Create Virtual Environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
```

## 3. Install CUDA-Enabled PyTorch

Do NOT hard-code a CUDA version. Detect and install:

```bash
# Detect CUDA version
CUDA_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
echo "Driver: $CUDA_VERSION"

# Install compatible PyTorch (check https://pytorch.org/get-started/locally/)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
# Adjust cu121 based on actual CUDA toolkit version

# Verify
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0)}')"
```

## 4. Install Remaining Dependencies

```bash
pip install -r requirements.lock
pip install -e .
```

## 5. GPU Doctor Checks

```bash
python -m traceai doctor --profile local
```

Must show:
- GPU: RTX A5000
- VRAM: ~24576 MB
- torch.cuda.is_available(): True

## 6. Download and Verify Model

```bash
python -m traceai download-model --profile local
# Verify hashes match model.lock.json
```

## 7. Safety Thresholds

Before any campaign:

```yaml
# config/profiles/local.yaml overrides for GPU
safety:
  max_gpu_memory_percent: 80  # 19.2 GB max
  max_host_ram_percent: 80
  max_test_duration_seconds: 600
  emergency_stop_file: workspace/EMERGENCY_STOP
```

Create emergency stop: `touch workspace/EMERGENCY_STOP` to halt all campaigns.

## 8. Quick GPU Campaign

```bash
python -m traceai rq4-campaign --profile local --quick --mode experimental
```

Expected: 3 trials × 4 configs × 20 requests = 240 real inference requests.
Duration: ~5-15 minutes depending on model load time.

## 9. Full GPU Campaign

```bash
python -m traceai rq4-campaign --profile local --mode experimental
```

Expected: 30 trials × 4 configs × 200 requests = 24,000 real inference requests.
Duration: ~2-6 hours.

## 10. Artifact Export

```bash
./scripts/export_campaign_bundle.sh
```

Produces: `campaign_bundle_<timestamp>.tar.gz` containing:
- results/rq4/
- generated/rq4/
- generated/environment.json
- model.lock.json

## 11. Environment Capture

Automatically saved by the campaign:
- GPU model, VRAM, driver version
- CUDA version
- PyTorch CUDA runtime version
- nvidia-smi snapshot during warmup
- Process GPU memory usage timeseries

## 12. Rollback/Stop Commands

```bash
# Emergency stop (creates file checked between trials)
touch workspace/EMERGENCY_STOP

# Kill service
pkill -f "uvicorn traceai.service.app"

# Check for orphan processes
ps aux | grep traceai
```

## 13. Validation

After campaign:

```bash
python -m traceai validate-publication --profile local --research-question RQ4
python -m traceai publication-readiness --profile local
```

RQ4 must show PASS_PUBLICATION_READY only if:
- Real HTTP inference confirmed
- GPU telemetry from NVML
- 30+ trials per configuration
- Raw observations traceable to request logs

## Notes

- Do NOT run on CPU and label results as GPU evidence
- Do NOT use _simulate_request() in experimental mode
- GPU memory timeseries must come from actual pynvml readings
- Results from this node will be labeled: "NVIDIA RTX A5000, CUDA <version>, Linux"
- Windows CPU results remain separate diagnostic evidence
