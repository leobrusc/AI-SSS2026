# GPU Campaign Runbook — NVIDIA L4

## Target Environment

- **GPU:** NVIDIA L4 Tensor Core GPU (approximately 24 GB GDDR6 memory)
- **OS:** Ubuntu 24.04.4 LTS (GCP)
- **CUDA:** Runtime-detected (do not hard-code version)
- **Python:** 3.12+
- **Model:** openai-community/gpt2 (124M parameters)

## Pre-Requisites

The following must be verified at runtime (not assumed):

```bash
nvidia-smi  # Must succeed
python -c "import torch; assert torch.cuda.is_available()"
python -c "import torch; print(torch.cuda.get_device_name(0))"
```

GPU name validation reads the expected regex from `config/profiles/gpu.yaml`:

```yaml
hardware:
  expected_gpu_name_regex: "NVIDIA L4"
  minimum_vram_mb: 22000
```

## 1. Clone or Update Repository

```bash
git clone git@github.com:leobrusc/traceai-ladc2026.git
cd traceai-ladc2026
git checkout traceai-gcp-l4-ready-v7
```

Or, if the repository already exists:

```bash
cd ~/traceai-ladc2026
git fetch origin --prune --tags
git checkout traceai-gcp-l4-ready-v7
```

## 2. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
```

## 3. Install CUDA-Enabled PyTorch

Do NOT hard-code a CUDA version. Do NOT infer from `nvidia-smi` CUDA compatibility version.

```bash
# Select the correct index URL from:
#   https://pytorch.org/get-started/locally/
# Then export it explicitly:
#   export TORCH_INDEX_URL=https://download.pytorch.org/whl/<cuXXX>
pip install torch torchvision --index-url "$TORCH_INDEX_URL"

# Verify
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0)}')"
```

## 4. Install Remaining Dependencies

```bash
pip install -e ".[dev,gpu]"
```

## 5. GPU Preflight Checks

```bash
python scripts/phase5_gpu_runbook.py
```

Must confirm:
- GPU matches profile regex (NVIDIA L4)
- VRAM >= 22000 MB
- torch.cuda.is_available(): True
- NVML telemetry operational
- No competing GPU processes

## 6. Download and Verify Model

```bash
python -m traceai download-model --profile gpu
```

Model revisions (immutable):
- Quick: `sshleifer/tiny-gpt2` @ `5f91d94bd9cd7190a9f3216ff93cd1dd95f2c7be`
- Full: `openai-community/gpt2` @ `607a30d783dfa663caf39e06633721c8d4cfcd7e`

## 7. Safety Thresholds

Configured in `config/profiles/gpu.yaml`:

```yaml
safety:
  max_cuda_oom_before_abort: 3
  max_service_restarts: 5
  max_consecutive_failures: 20
  abort_on_unrecovered_service: true
  require_no_mock: true
  require_real_http_inference: true
```

Emergency stop: `touch workspace/EMERGENCY_STOP` halts all campaigns.

## 8. Quick GPU Campaign

```bash
bash scripts/run_gpu_campaign.sh
# OR directly:
python -m traceai rq4-campaign --profile gpu --quick --mode experimental
```

Expected: 3 trials × 4 configs × 20 requests = 240 real inference requests.

## 9. Full GPU Campaign

```bash
bash scripts/run_gpu_campaign.sh --run-full
# OR directly:
python -m traceai rq4-campaign --profile gpu --mode experimental
```

Expected: 30 trials × 4 configs × 200 requests = 24,000 real inference requests.

## 10. Artifact Export

```bash
./scripts/export_campaign_bundle.sh
```

Produces: `campaign_bundle_<timestamp>.tar.gz`

## 11. Environment Capture

Automatically saved by the campaign:
- GPU model, VRAM, driver version
- CUDA version
- PyTorch CUDA runtime version
- nvidia-smi snapshot during warmup
- Process GPU memory usage timeseries

## 12. Rollback/Stop Commands

```bash
# Emergency stop
touch workspace/EMERGENCY_STOP

# Kill service
pkill -f "uvicorn traceai.service.app"

# Check for orphan processes
ps aux | grep traceai
```

## 13. Validation

After campaign:

```bash
python -m traceai validate-publication --profile gpu --research-question RQ4
python -m traceai publication-readiness --profile gpu
```

RQ4 must show PASS_PUBLICATION_READY only if:
- Real HTTP inference confirmed
- GPU telemetry from NVML
- 30+ trials per configuration
- Raw observations traceable to request logs

## Notes

- The final GPU campaign is executed on a GCP node equipped with one
  NVIDIA L4 Tensor Core GPU and approximately 24 GB of GDDR6 memory.
- Do NOT run on CPU and label results as GPU evidence.
- Do NOT use `_simulate_request()` in experimental mode.
- GPU memory timeseries must come from actual pynvml readings.
- Results from this node will be labeled: "NVIDIA L4, CUDA <version>, Linux"
- Windows CPU results remain separate diagnostic evidence.
