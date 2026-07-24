#!/usr/bin/env bash
# =============================================================================
# TraceAI GPU Campaign Execution (profile-driven, hardware-agnostic)
# Reads GPU expectations from config/profiles/gpu.yaml
#
# Usage:
#   bash scripts/run_gpu_campaign.sh --in-place              # Quick (default)
#   bash scripts/run_gpu_campaign.sh --in-place --run-full   # Full 30-trial
#   bash scripts/run_gpu_campaign.sh --clone <url> [dir]     # Clone mode
#
# Environment:
#   VENV_DIR    Virtual environment directory (default: .venv-gpu)
#   TRACEAI_DEVICE  Device override (default: read from profile)
#   TORCH_INDEX_URL  PyTorch CUDA wheel index (required only if CUDA torch absent)
# =============================================================================
set -Eeuo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
VENV_DIR="${VENV_DIR:-.venv-gpu}"
RUN_FULL=false
MODE="in-place"
CLONE_URL=""
CLONE_DIR=""

# Model revisions (immutable)
TINY_MODEL="sshleifer/tiny-gpt2"
TINY_REVISION="5f91d94bd9cd7190a9f3216ff93cd1dd95f2c7be"
FULL_MODEL="openai-community/gpt2"
FULL_REVISION="607a30d783dfa663caf39e06633721c8d4cfcd7e"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --run-full)   RUN_FULL=true; shift ;;
        --in-place)   MODE="in-place"; shift ;;
        --clone)      MODE="clone"; shift
                      CLONE_URL="${1:-}"; shift
                      CLONE_DIR="${1:-}"; shift ;;
        *)            shift ;;
    esac
done

timestamp() { date -u +"%Y-%m-%dT%H:%M:%S%z"; }

# ---------------------------------------------------------------------------
# Resolve working directory
# ---------------------------------------------------------------------------
if [ "$MODE" = "clone" ]; then
    if [ -z "$CLONE_URL" ]; then
        echo "ERROR: --clone requires a repository URL."
        exit 1
    fi
    CLONE_DIR="${CLONE_DIR:-$(basename "$CLONE_URL" .git)}"
    if [ -d "$CLONE_DIR" ]; then
        echo "ERROR: $CLONE_DIR exists. Remove it first or specify a different path."
        exit 1
    fi
    # Prevent nested clone inside own repo
    if git rev-parse --is-inside-work-tree &>/dev/null; then
        REPO_ROOT=$(git rev-parse --show-toplevel)
        TARGET_ABS=$(cd "$(dirname "$CLONE_DIR")" && pwd)/$(basename "$CLONE_DIR")
        if [[ "$TARGET_ABS" == "$REPO_ROOT"* ]]; then
            echo "ERROR: Cannot clone inside the current repository ($REPO_ROOT)."
            exit 1
        fi
    fi
    git clone "$CLONE_URL" "$CLONE_DIR"
    cd "$CLONE_DIR"
elif [ "$MODE" = "in-place" ]; then
    # Validate we are in a git repository
    if ! git rev-parse --is-inside-work-tree &>/dev/null; then
        echo "ERROR: Not inside a git repository. Use --clone or cd into the repo."
        exit 1
    fi
    cd "$(git rev-parse --show-toplevel)"
else
    echo "ERROR: Unknown mode. Use --in-place or --clone."
    exit 1
fi

# ---------------------------------------------------------------------------
# Resolve current ref
# ---------------------------------------------------------------------------
CURRENT_COMMIT=$(git rev-parse HEAD)
CURRENT_TAG=$(git describe --tags --exact-match 2>/dev/null || echo "untagged")
CURRENT_SHORT=$(git rev-parse --short HEAD)

if [ "$CURRENT_TAG" = "untagged" ]; then
    echo "WARNING: HEAD is not at an exact tag. Commit: $CURRENT_SHORT"
    echo "         Results will reference commit $CURRENT_COMMIT"
fi

echo "==================================================================="
echo "  TraceAI GPU Campaign"
echo "  Started: $(timestamp)"
echo "  Ref: ${CURRENT_TAG} (${CURRENT_SHORT})"
echo "  Mode: $([ "$RUN_FULL" = true ] && echo 'FULL' || echo 'QUICK (use --run-full for full campaign)')"
echo "  Venv: ${VENV_DIR}"
echo "==================================================================="

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

echo "--- nvidia-smi ---"
nvidia-smi
echo ""

echo "--- GPU Details ---"
nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free,memory.used,temperature.gpu,utilization.gpu --format=csv \
    | tee generated/gpu/gpu_info.csv
echo ""

GPU_MODEL=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
VRAM_TOTAL=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
VRAM_FREE=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)

echo "GPU: $GPU_MODEL | Driver: $DRIVER_VERSION | VRAM: ${VRAM_TOTAL}/${VRAM_FREE} MiB (total/free)"
echo ""

# Save preflight record
cat > generated/gpu/preflight_record.txt <<EOF
Preflight Timestamp: $(timestamp)
OS: $(uname -a)
Driver: $DRIVER_VERSION
GPU: $GPU_MODEL
VRAM Total: ${VRAM_TOTAL} MiB
VRAM Free: ${VRAM_FREE} MiB
Commit: $CURRENT_COMMIT
Tag: $CURRENT_TAG
Venv: $VENV_DIR
EOF

echo ""

# =============================================================================
# PHASE 2: Virtual Environment and PyTorch CUDA
# =============================================================================
echo ""
echo ">>> PHASE 2: Virtual Environment and PyTorch CUDA"
echo ""

# Create venv only if it does not exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip setuptools wheel -q

# --- Check if CUDA-enabled PyTorch is already installed ---
PYTORCH_READY=false
if python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo "Existing CUDA-enabled PyTorch detected. Skipping reinstall."
    PYTORCH_VERSION=$(python -c "import torch; print(torch.__version__)")
    PYTORCH_CUDA=$(python -c "import torch; print(torch.version.cuda)")
    echo "  torch==$PYTORCH_VERSION (CUDA $PYTORCH_CUDA)"
    PYTORCH_READY=true
fi

if [ "$PYTORCH_READY" = false ]; then
    if [ -z "${TORCH_INDEX_URL:-}" ]; then
        echo "============================================================"
        echo "  ERROR: No CUDA-enabled PyTorch found and TORCH_INDEX_URL"
        echo "  is not set."
        echo ""
        echo "  Select the correct index URL from:"
        echo "    https://pytorch.org/get-started/locally/"
        echo ""
        echo "  Then re-run with:"
        echo "    TORCH_INDEX_URL=https://download.pytorch.org/whl/<cuXXX> \\"
        echo "        bash scripts/run_gpu_campaign.sh --in-place"
        echo ""
        echo "  Do NOT infer from the nvidia-smi CUDA compatibility version."
        echo "============================================================"
        exit 1
    fi

    echo "Installing PyTorch from: $TORCH_INDEX_URL"
    pip install torch torchvision torchaudio --index-url "$TORCH_INDEX_URL"

    PYTORCH_VERSION=$(python -c "import torch; print(torch.__version__)")
    PYTORCH_CUDA=$(python -c "import torch; print(torch.version.cuda)")
fi

# Install project (no-deps to avoid overwriting torch)
pip install -e . --no-deps -q

# Install remaining non-torch dependencies
pip install $(python -c "
import tomllib
with open('pyproject.toml', 'rb') as f:
    d = tomllib.load(f)
deps = d.get('project', {}).get('dependencies', [])
for dep in deps:
    if 'torch' not in dep.lower():
        print(dep)
" | tr '\n' ' ') -q

# GPU extras (nvidia-ml-py only)
pip install nvidia-ml-py -q
pip install pytest httpx psutil -q

# Verify no breakage
python -m pip check

echo ""
echo "Phase 2 complete: PyTorch CUDA validated."
echo ""

# =============================================================================
# PHASE 3: Validation Gates
# =============================================================================
echo ""
echo ">>> PHASE 3: PyTorch CUDA Validation Gates"
echo ""

python - <<'PY'
import sys
import os
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
echo "Phase 3 complete."

# =============================================================================
# PHASE 4: Quick GPU Campaign
# =============================================================================
echo ""
echo ">>> PHASE 4: Quick GPU Campaign"
echo ""

export TRACEAI_DEVICE="${TRACEAI_DEVICE:-cuda}"

python -m traceai rq4-campaign \
    --profile gpu \
    --quick \
    --mode experimental

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
    echo "    bash scripts/run_gpu_campaign.sh --in-place --run-full"
    echo ""
    # Save manifest
    python - <<PY
import json, torch
manifest = {
    "torch_version": torch.__version__,
    "torch_cuda": torch.version.cuda,
    "gpu": "$GPU_MODEL",
    "tag": "$CURRENT_TAG",
    "commit": "$CURRENT_COMMIT",
    "venv": "$VENV_DIR",
    "mode": "quick",
}
with open("generated/gpu/campaign_manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
PY
    echo "==================================================================="
    echo "  Quick Validation Complete"
    echo "  Commit: ${CURRENT_SHORT}"
    echo "  Ref: ${CURRENT_TAG}"
    echo "  Finished: $(timestamp)"
    echo "==================================================================="
    exit 0
fi

echo "All quick validation gates passed. Proceeding with full campaign."
echo ""

python -m traceai rq4-campaign \
    --profile gpu \
    --mode experimental

echo ""
echo "Phase 5 complete: Full campaign finished."

# =============================================================================
# PHASE 6: Manifest and Analysis
# =============================================================================
echo ""
echo ">>> PHASE 6: Manifest and Analysis"
echo ""

python - <<PY
import json, torch
manifest = {
    "torch_version": torch.__version__,
    "torch_cuda": torch.version.cuda,
    "gpu": "$GPU_MODEL",
    "tag": "$CURRENT_TAG",
    "commit": "$CURRENT_COMMIT",
    "venv": "$VENV_DIR",
    "mode": "full",
}
with open("generated/gpu/campaign_manifest.json", "w") as f:
    json.dump(manifest, f, indent=2)
PY

python -m traceai analyze --profile gpu 2>/dev/null || \
    echo "Analysis: run manually with 'python -m traceai analyze --profile gpu'"

echo ""
echo "==================================================================="
echo "  Campaign Complete"
echo "  Commit: ${CURRENT_SHORT}"
echo "  Ref: ${CURRENT_TAG}"
echo "  Finished: $(timestamp)"
echo "==================================================================="
