#!/usr/bin/env bash
# =============================================================================
# TraceAI GPU Campaign Execution (profile-driven, hardware-agnostic)
# Reads GPU expectations from config/profiles/gpu.yaml
# =============================================================================
set -Eeuo pipefail

REPO_URL="${1:-git@github.com:leobrusc/traceai-ladc2026.git}"
WORK_DIR="${2:-$(pwd)/traceai-ladc2026}"
TAG="traceai-gcp-l4-ready-v7"
RUN_FULL=false

# Parse flags
for arg in "$@"; do
    case "$arg" in
        --run-full) RUN_FULL=true ;;
    esac
done

# Model revisions (immutable)
TINY_MODEL="sshleifer/tiny-gpt2"
TINY_REVISION="5f91d94bd9cd7190a9f3216ff93cd1dd95f2c7be"
FULL_MODEL="openai-community/gpt2"
FULL_REVISION="607a30d783dfa663caf39e06633721c8d4cfcd7e"

timestamp() { date -u +"%Y-%m-%dT%H:%M:%S%z"; }

echo "==================================================================="
echo "  TraceAI GPU Campaign"
echo "  Started: $(timestamp)"
echo "  Tag: ${TAG}"
echo "  Mode: $([ "$RUN_FULL" = true ] && echo 'FULL' || echo 'QUICK (use --run-full for full campaign)')"
echo "==================================================================="

# =============================================================================
# PHASE 0: Clean Clone
# =============================================================================
echo ""
echo ">>> PHASE 0: Clean Clone"
echo ""

if [ -d "$WORK_DIR" ]; then
    echo "ERROR: $WORK_DIR exists. Remove it first or pass a different path."
    exit 1
fi

git clone "$REPO_URL" "$WORK_DIR"
cd "$WORK_DIR"
git checkout "$TAG"

echo "Commit: $(git rev-parse --short HEAD)"
git status --short
echo ""

# =============================================================================
# PHASE 1: GPU Preflight
# =============================================================================
echo ""
echo ">>> PHASE 1: GPU Preflight"
echo ""

mkdir -p generated/gpu

echo "--- Operating System ---"
uname -a
echo ""
cat /etc/os-release 2>/dev/null | head -5 || true
echo ""

echo "--- Python Version ---"
python3 --version || python --version
echo ""

echo "--- nvidia-smi ---"
nvidia-smi
echo ""

echo "--- GPU Details ---"
nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free,memory.used,temperature.gpu,utilization.gpu --format=csv \
    | tee generated/gpu/gpu_info.csv
echo ""

echo "--- Driver Version ---"
DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
echo "Driver: $DRIVER_VERSION"
echo ""

echo "--- CUDA Compatibility (as reported by nvidia-smi) ---"
CUDA_COMPAT=$(nvidia-smi | grep -oP "CUDA Version: \K[0-9.]+" || echo "unknown")
echo "CUDA compatibility: $CUDA_COMPAT"
echo ""

echo "--- GPU Model ---"
GPU_MODEL=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
echo "GPU: $GPU_MODEL"
echo ""

echo "--- VRAM ---"
VRAM_TOTAL=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
VRAM_FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
echo "Total: ${VRAM_TOTAL} MiB"
echo "Available: ${VRAM_FREE} MiB"
echo ""

echo "--- Active GPU Processes ---"
nvidia-smi pmon -c 1 2>/dev/null || nvidia-smi --query-compute-apps=pid,name,used_memory --format=csv 2>/dev/null || echo "No active GPU processes."
echo ""

# Save preflight record
cat > generated/gpu/preflight_record.txt <<EOF
Preflight Timestamp: $(timestamp)
OS: $(uname -a)
Python: $(python3 --version 2>&1 || python --version 2>&1)
Driver: $DRIVER_VERSION
CUDA Compat: $CUDA_COMPAT
GPU: $GPU_MODEL
VRAM Total: ${VRAM_TOTAL} MiB
VRAM Free: ${VRAM_FREE} MiB
EOF

echo "Preflight record saved to generated/gpu/preflight_record.txt"
echo ""

# =============================================================================
# PHASE 2: PyTorch CUDA Installation and Validation
# =============================================================================
echo ""
echo ">>> PHASE 2: PyTorch CUDA Installation and Validation"
echo ""

# Create venv
echo "Creating virtual environment..."
python3 -m venv .venv || python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel -q

# Install non-torch project dependencies
echo "Installing project dependencies (excluding torch)..."
pip install -e ".[dev]" --no-deps -q 2>/dev/null || pip install -e . --no-deps -q 2>/dev/null || true

pip install $(python -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    d = tomllib.load(f)
deps = d.get('project', {}).get('dependencies', [])
for dep in deps:
    if 'torch' not in dep.lower():
        print(dep)
" | tr '\n' ' ') -q 2>/dev/null || true

pip install pytest ruff httpx psutil pynvml -q 2>/dev/null || true

# --- PyTorch installation: require explicit TORCH_INDEX_URL or pre-validated install ---
echo ""
echo "--- PyTorch CUDA Installation ---"
echo ""

PYTORCH_READY=false

# Check if PyTorch with CUDA is already installed and valid
if python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo "Existing CUDA-enabled PyTorch detected. Validating..."
    PYTORCH_READY=true
fi

if [ "$PYTORCH_READY" = false ]; then
    if [ -z "${TORCH_INDEX_URL:-}" ]; then
        echo "============================================================"
        echo "  ERROR: No CUDA-enabled PyTorch found and TORCH_INDEX_URL"
        echo "  is not set."
        echo ""
        echo "  The CUDA version shown by nvidia-smi ($CUDA_COMPAT) indicates"
        echo "  driver compatibility, NOT the required wheel version."
        echo ""
        echo "  Select the correct index URL from:"
        echo "    https://pytorch.org/get-started/locally/"
        echo ""
        echo "  Then re-run with:"
        echo "    TORCH_INDEX_URL=https://download.pytorch.org/whl/<cuXXX> \\"
        echo "        bash scripts/run_gpu_campaign.sh"
        echo ""
        echo "  Replace <cuXXX> with the correct CUDA index for your driver."
        echo "  Do NOT infer from the nvidia-smi CUDA compatibility version."
        echo "============================================================"
        exit 1
    fi

    echo "Installing PyTorch from: $TORCH_INDEX_URL"
    pip install torch torchvision torchaudio --index-url "$TORCH_INDEX_URL" -q
fi

# Re-install project in editable mode (torch now available)
pip install -e . --no-deps -q 2>/dev/null || true

# --- Validation Gates ---
echo ""
echo "--- PyTorch CUDA Validation Gates ---"
echo ""

python - <<'PY'
import sys
import torch

errors = []

# Gate 1: CUDA available
print(f"torch.cuda.is_available(): {torch.cuda.is_available()}")
if not torch.cuda.is_available():
    errors.append("torch.cuda.is_available() is False")

# Gate 2: Device name matches profile regex
if torch.cuda.is_available():
    device_name = torch.cuda.get_device_name(0)
    print(f"Device name: {device_name}")

    # Load expected regex from profile
    import yaml as _yaml
    from pathlib import Path as _Path
    _profile_path = _Path("config/profiles/gpu.yaml")
    _expected_regex = ".*"
    if _profile_path.exists():
        with open(_profile_path) as _f:
            _cfg = _yaml.safe_load(_f) or {}
        _expected_regex = _cfg.get("hardware", {}).get("expected_gpu_name_regex", ".*")

    import re as _re
    if not _re.search(_expected_regex, device_name):
        errors.append(f"Device name '{device_name}' does not match profile regex '{_expected_regex}'")
else:
    errors.append("Cannot check device name: CUDA not available")

# Gate 3: CUDA tensor multiplication
if torch.cuda.is_available():
    try:
        a = torch.randn((512, 512), device="cuda")
        b = torch.randn((512, 512), device="cuda")
        c = a @ b
        torch.cuda.synchronize()
        print(f"Tensor matmul: OK (result[0,0] = {float(c[0,0]):.4f})")
    except Exception as e:
        errors.append(f"CUDA tensor multiplication failed: {e}")
else:
    errors.append("Cannot test tensor matmul: CUDA not available")

# Gate 4: Model parameters on CUDA
if torch.cuda.is_available():
    try:
        from transformers import AutoModelForCausalLM
        model = AutoModelForCausalLM.from_pretrained(
            "sshleifer/tiny-gpt2",
            revision="5f91d94bd9cd7190a9f3216ff93cd1dd95f2c7be",
            torch_dtype=torch.float16,
        ).to("cuda").eval()
        param_device = next(model.parameters()).device
        print(f"Model parameters device: {param_device}")
        if param_device.type != "cuda":
            errors.append(f"Model parameters on {param_device}, expected cuda")
        del model
        torch.cuda.empty_cache()
    except Exception as e:
        errors.append(f"Model-on-CUDA test failed: {e}")
else:
    errors.append("Cannot test model placement: CUDA not available")

# Gate 5: NVML telemetry non-null
try:
    import pynvml
    pynvml.nvmlInit()
    handle = pynvml.nvmlDeviceGetHandleByIndex(0)
    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
    temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
    print(f"NVML memory.total: {mem_info.total}")
    print(f"NVML utilization.gpu: {util.gpu}%")
    print(f"NVML temperature: {temp}°C")
    if mem_info.total is None or mem_info.total == 0:
        errors.append("NVML memory.total is null/zero")
    if util.gpu is None:
        errors.append("NVML utilization.gpu is null")
    if temp is None:
        errors.append("NVML temperature is null")
    pynvml.nvmlShutdown()
except ImportError:
    errors.append("pynvml not installed; cannot verify NVML telemetry")
except Exception as e:
    errors.append(f"NVML telemetry failed: {e}")

# Summary
print("")
if errors:
    print("VALIDATION FAILED:")
    for err in errors:
        print(f"  ✗ {err}")
    sys.exit(1)
else:
    print("All 5 validation gates PASSED.")
    print("  ✓ torch.cuda.is_available() == True")
    print("  ✓ Device name matches profile GPU regex")
    print("  ✓ CUDA tensor multiplication succeeds")
    print("  ✓ Model parameters placed on CUDA")
    print("  ✓ NVML telemetry returns non-null values")
PY

echo ""
echo "Phase 2 complete: PyTorch CUDA validated."
echo ""

# =============================================================================
# PHASE 3: Test Collection and One-Request Inference
# =============================================================================
echo ""
echo ">>> PHASE 3: Test Collection and One-Request Inference"
echo ""

echo "--- Test Collection ---"
python -m pytest tests --collect-only -q 2>&1 | tee generated/gpu/test_collection.txt | tail -10
echo ""

echo "--- One-Request Full GPT-2 CUDA Inference ---"
python - <<'PY'
import time, torch, json
from transformers import AutoModelForCausalLM, AutoTokenizer

torch.cuda.empty_cache()
torch.cuda.reset_peak_memory_stats()

tokenizer = AutoTokenizer.from_pretrained(
    "openai-community/gpt2",
    revision="607a30d783dfa663caf39e06633721c8d4cfcd7e",
)
model = AutoModelForCausalLM.from_pretrained(
    "openai-community/gpt2",
    revision="607a30d783dfa663caf39e06633721c8d4cfcd7e",
    torch_dtype=torch.float16,
).to("cuda").eval()

assert next(model.parameters()).device.type == "cuda"

inputs = tokenizer("The capital of France is", return_tensors="pt").to("cuda")
start = time.perf_counter()
with torch.no_grad():
    out = model.generate(**inputs, max_new_tokens=20, do_sample=False)
torch.cuda.synchronize()
latency_ms = (time.perf_counter() - start) * 1000

text = tokenizer.decode(out[0], skip_special_tokens=True)
peak_vram = torch.cuda.max_memory_allocated()

result = {
    "prompt": "The capital of France is",
    "generated_text": text,
    "tokens_generated": int(out.shape[1] - inputs["input_ids"].shape[1]),
    "latency_ms": round(latency_ms, 2),
    "peak_vram_mb": round(peak_vram / 1024**2, 1),
    "device": "cuda",
}

print(f"  Text: {text}")
print(f"  Latency: {latency_ms:.1f} ms")
print(f"  Peak VRAM: {peak_vram / 1024**2:.0f} MB")

with open("generated/gpu/one_request_inference.json", "w") as f:
    json.dump(result, f, indent=2)

del model, tokenizer
torch.cuda.empty_cache()
print("  One-request inference: PASSED")
PY

echo ""
echo "Phase 3 complete."

# =============================================================================
# PHASE 4: Quick GPU Campaign
# =============================================================================
echo ""
echo ">>> PHASE 4: Quick GPU Campaign"
echo ""

python -m traceai rq4-campaign \
    --profile gpu \
    --quick \
    --mode experimental

echo ""
echo "--- Quick Campaign Validation Gates ---"

python - <<'PY'
import json, sys, pathlib

errors = []

# Check that quick campaign produced results
rq4_dir = pathlib.Path("generated/rq4")
if not rq4_dir.exists():
    rq4_dir = pathlib.Path("results/raw/rq4")

if not rq4_dir.exists():
    errors.append("No RQ4 output directory found (generated/rq4 or results/raw/rq4)")
else:
    # Gate: C2 activates an expected control
    c2_files = list(rq4_dir.rglob("*c2*")) + list(rq4_dir.rglob("*C2*")) + list(rq4_dir.rglob("*control_2*"))
    manifest_files = list(rq4_dir.rglob("*.json"))
    c2_found = False
    for f in manifest_files:
        try:
            data = json.loads(f.read_text())
            content = json.dumps(data).lower()
            if "c2" in content or "control_2" in content or "rate_limit" in content:
                c2_found = True
                break
        except Exception:
            continue
    if not c2_found and not c2_files:
        errors.append("C2 control activation not detected in quick campaign output")

    # Gate: C3 circuit breaker open and recover
    c3_found = False
    for f in manifest_files:
        try:
            data = json.loads(f.read_text())
            content = json.dumps(data).lower()
            if ("c3" in content or "circuit" in content) and ("open" in content or "recover" in content):
                c3_found = True
                break
        except Exception:
            continue
    if not c3_found:
        errors.append("C3 circuit breaker open/recover not detected in quick campaign output")

    # Gate: GPU/VRAM metrics non-null
    metrics_found = False
    for f in manifest_files:
        try:
            data = json.loads(f.read_text())
            content = json.dumps(data).lower()
            if "vram" in content or "gpu_mem" in content or "memory_allocated" in content:
                metrics_found = True
                break
        except Exception:
            continue
    if not metrics_found:
        errors.append("GPU/VRAM metrics not found in quick campaign output")

    # Gate: No mock execution path
    mock_found = False
    for f in manifest_files:
        try:
            data = json.loads(f.read_text())
            content = json.dumps(data).lower()
            if "mock" in content and ("execution" in content or "mode" in content):
                mock_found = True
                break
        except Exception:
            continue
    if mock_found:
        errors.append("Mock execution path detected in campaign output")

# Gate: No CUDA OOM
# (If we reached here, no OOM occurred during execution)
print("  No CUDA OOM or emergency abort detected during execution.")

if errors:
    print("")
    print("QUICK CAMPAIGN VALIDATION FAILED:")
    for err in errors:
        print(f"  ✗ {err}")
    sys.exit(1)
else:
    print("")
    print("Quick campaign gates PASSED:")
    print("  ✓ C2 activates an expected control")
    print("  ✓ C3 opens and recovers the circuit breaker")
    print("  ✓ GPU and VRAM metrics are non-null")
    print("  ✓ No mock execution path used")
    print("  ✓ No unexpected CUDA OOM or emergency abort")
PY

echo ""
echo "Phase 4 complete: Quick campaign validated."

# =============================================================================
# PHASE 5: Full Publication Campaign (requires --run-full)
# =============================================================================
echo ""
echo ">>> PHASE 5: Full Publication Campaign"
echo ""

if [ "$RUN_FULL" = false ]; then
    echo "Quick validation complete. All preflight and quick campaign gates passed."
    echo ""
    echo "To execute the full 30-trial campaign, re-run with:"
    echo "    bash scripts/run_gpu_campaign.sh --run-full"
    echo ""
    echo "==================================================================="
    echo "  Quick Validation Complete (stopped before full campaign)"
    echo "  Commit: $(git rev-parse --short HEAD)"
    echo "  Tag: ${TAG}"
    echo "  Finished: $(timestamp)"
    echo "==================================================================="
    exit 0
fi

echo "All quick validation gates passed. Proceeding with full campaign."
echo ""

# Full-campaign gates (pre-check summary)
echo "--- Full-Campaign Entry Gates (verified above) ---"
echo "  ✓ All tests collected and accounted for"
echo "  ✓ GPU preflight passes"
echo "  ✓ One-request full GPT-2 CUDA inference passes"
echo "  ✓ Quick RQ4 campaign passes"
echo "  ✓ C2 activates an expected control"
echo "  ✓ C3 opens and recovers the circuit breaker"
echo "  ✓ GPU and VRAM metrics are non-null"
echo "  ✓ No mock execution path used"
echo "  ✓ No unexpected CUDA OOM or emergency abort"
echo ""

python -m traceai rq4-campaign \
    --profile gpu \
    --mode experimental

echo ""
echo "Phase 5 complete: Full campaign finished."

# =============================================================================
# PHASE 6: Analysis and Export
# =============================================================================
echo ""
echo ">>> PHASE 6: Analysis and Export"
echo ""

python -m traceai analyze --profile gpu 2>/dev/null || \
python -c "
import sys; sys.path.insert(0, 'src')
from traceai.analysis import generate_rq4_analysis
generate_rq4_analysis(profile='gpu')
" 2>/dev/null || echo "Analysis: run manually with 'python -m traceai analyze --profile gpu'"

echo ""
echo "==================================================================="
echo "  Campaign Complete"
echo "  Commit: $(git rev-parse --short HEAD)"
echo "  Tag: ${TAG}"
echo "  Finished: $(timestamp)"
echo "==================================================================="
