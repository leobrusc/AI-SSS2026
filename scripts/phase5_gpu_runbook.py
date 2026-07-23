"""Phase 5: GPU Runbook — Environment detection and preflight checks.

Reads GPU hardware expectations from config/profiles/gpu.yaml.
Removes hard-coded CUDA/PyTorch wheel assumptions.
Provides runtime GPU validation before expensive experiments.
"""
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "generated" / "gpu_runbook"
OUT_DIR.mkdir(parents=True, exist_ok=True)

GPU_PROFILE_PATH = ROOT / "config" / "profiles" / "gpu.yaml"


def _load_gpu_profile() -> dict:
    """Load the GPU profile config. Returns empty dict on failure."""
    if GPU_PROFILE_PATH.exists():
        with open(GPU_PROFILE_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def _get_hardware_config() -> dict:
    """Get hardware expectations from profile."""
    profile = _load_gpu_profile()
    hw = profile.get("hardware", {})
    return {
        "expected_gpu_name_regex": hw.get("expected_gpu_name_regex", ".*"),
        "minimum_vram_mb": hw.get("minimum_vram_mb", 2048),
        "expected_gpu_count": hw.get("expected_gpu_count", 1),
    }


# ===========================================================================
# GPU preflight checks
# ===========================================================================

class PreflightResult:
    """Result of a single preflight check."""

    def __init__(self, name: str, passed: bool, message: str,
                 severity: str = "blocker", details: Optional[dict] = None):
        self.name = name
        self.passed = passed
        self.message = message
        self.severity = severity  # blocker, warning, info
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "severity": self.severity,
            "details": self.details,
        }


def check_torch_installed() -> PreflightResult:
    """Check that PyTorch is installed."""
    try:
        import torch
        return PreflightResult(
            "torch_installed", True,
            f"PyTorch {torch.__version__} installed",
            severity="info",
            details={"version": torch.__version__},
        )
    except ImportError:
        return PreflightResult(
            "torch_installed", False,
            "PyTorch not installed",
            severity="blocker",
        )


def check_cuda_available() -> PreflightResult:
    """Check CUDA availability via PyTorch and validate GPU name against profile."""
    try:
        import torch
        available = torch.cuda.is_available()
        if available:
            device_name = torch.cuda.get_device_name(0)
            cuda_ver = torch.version.cuda or "unknown"
            hw = _get_hardware_config()
            gpu_regex = hw["expected_gpu_name_regex"]
            name_matches = bool(re.search(gpu_regex, device_name))
            return PreflightResult(
                "cuda_available", True,
                f"CUDA available: {device_name} (CUDA {cuda_ver})",
                severity="info",
                details={
                    "device_name": device_name,
                    "cuda_version": cuda_ver,
                    "device_count": torch.cuda.device_count(),
                    "expected_gpu_regex": gpu_regex,
                    "gpu_name_matches_profile": name_matches,
                },
            )
        else:
            return PreflightResult(
                "cuda_available", False,
                "CUDA not available (torch.cuda.is_available() = False)",
                severity="warning",
                details={"reason": "No CUDA-capable GPU detected by PyTorch"},
            )
    except ImportError:
        return PreflightResult(
            "cuda_available", False,
            "Cannot check CUDA: PyTorch not installed",
            severity="blocker",
        )


def check_cuda_torch_compatibility() -> PreflightResult:
    """Verify PyTorch CUDA version matches driver capabilities."""
    try:
        import torch
        if not torch.cuda.is_available():
            return PreflightResult(
                "cuda_torch_compat", True,
                "N/A (CPU mode — no compatibility issue)",
                severity="info",
                details={"mode": "cpu"},
            )

        torch_cuda = torch.version.cuda
        # Try a simple CUDA operation
        try:
            x = torch.zeros(1, device="cuda")
            del x
            return PreflightResult(
                "cuda_torch_compat", True,
                f"PyTorch CUDA {torch_cuda} operational (tensor allocation verified)",
                severity="info",
                details={"torch_cuda_version": torch_cuda, "tensor_test": "passed"},
            )
        except RuntimeError as e:
            return PreflightResult(
                "cuda_torch_compat", False,
                f"CUDA runtime error: {str(e)[:100]}",
                severity="blocker",
                details={"error": str(e)[:200], "torch_cuda_version": torch_cuda},
            )
    except ImportError:
        return PreflightResult(
            "cuda_torch_compat", False,
            "Cannot check: PyTorch not installed",
            severity="blocker",
        )


def check_vram_sufficient(min_mb: Optional[int] = None) -> PreflightResult:
    """Check if GPU has sufficient VRAM per the profile configuration."""
    if min_mb is None:
        hw = _get_hardware_config()
        min_mb = hw["minimum_vram_mb"]
    try:
        import torch
        if not torch.cuda.is_available():
            return PreflightResult(
                "vram_sufficient", True,
                "N/A (CPU mode)",
                severity="info",
                details={"mode": "cpu"},
            )

        total = torch.cuda.get_device_properties(0).total_mem
        total_mb = total / (1024**2)
        if total_mb >= min_mb:
            return PreflightResult(
                "vram_sufficient", True,
                f"VRAM: {total_mb:.0f} MB >= {min_mb} MB required",
                severity="info",
                details={"total_mb": round(total_mb), "required_mb": min_mb},
            )
        else:
            return PreflightResult(
                "vram_sufficient", False,
                f"VRAM: {total_mb:.0f} MB < {min_mb} MB required",
                severity="blocker",
                details={"total_mb": round(total_mb), "required_mb": min_mb},
            )
    except ImportError:
        return PreflightResult(
            "vram_sufficient", False,
            "Cannot check: PyTorch not installed",
            severity="blocker",
        )


def check_nvidia_driver() -> PreflightResult:
    """Check nvidia-smi availability and driver version."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version,name,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(",")
            driver = parts[0].strip() if parts else "unknown"
            return PreflightResult(
                "nvidia_driver", True,
                f"NVIDIA driver {driver} detected",
                severity="info",
                details={"driver_version": driver, "raw": result.stdout.strip()},
            )
        else:
            return PreflightResult(
                "nvidia_driver", False,
                "nvidia-smi failed (no NVIDIA driver?)",
                severity="warning",
                details={"returncode": result.returncode},
            )
    except FileNotFoundError:
        return PreflightResult(
            "nvidia_driver", False,
            "nvidia-smi not found in PATH",
            severity="warning",
            details={"hint": "Install NVIDIA driver or ensure nvidia-smi is in PATH"},
        )
    except subprocess.TimeoutExpired:
        return PreflightResult(
            "nvidia_driver", False,
            "nvidia-smi timed out",
            severity="warning",
        )


def check_torch_device_config() -> PreflightResult:
    """Verify the TRACEAI_DEVICE setting is valid."""
    import os
    device = os.environ.get("TRACEAI_DEVICE", "auto")

    valid_devices = {"auto", "cpu", "cuda", "cuda:0", "cuda:1", "mps"}
    if device in valid_devices:
        return PreflightResult(
            "device_config", True,
            f"TRACEAI_DEVICE='{device}' (valid)",
            severity="info",
            details={"device": device},
        )
    else:
        return PreflightResult(
            "device_config", False,
            f"TRACEAI_DEVICE='{device}' is not recognized",
            severity="warning",
            details={"device": device, "valid": sorted(valid_devices)},
        )


def check_model_loadable(model_id: str = "sshleifer/tiny-gpt2") -> PreflightResult:
    """Check if the target model can be loaded (quick validation only)."""
    try:
        from transformers import AutoConfig
        config = AutoConfig.from_pretrained(model_id)
        return PreflightResult(
            "model_loadable", True,
            f"Model config loaded: {model_id} ({config.model_type})",
            severity="info",
            details={"model_id": model_id, "model_type": config.model_type},
        )
    except Exception as e:
        return PreflightResult(
            "model_loadable", False,
            f"Cannot load model config: {str(e)[:100]}",
            severity="blocker",
            details={"model_id": model_id, "error": str(e)[:200]},
        )


def check_gpu_name_matches() -> PreflightResult:
    """Verify detected GPU name matches the profile regex."""
    hw = _get_hardware_config()
    gpu_regex = hw["expected_gpu_name_regex"]
    try:
        import torch
        if not torch.cuda.is_available():
            return PreflightResult(
                "gpu_name_matches", True,
                f"N/A (CPU mode, profile expects: {gpu_regex})",
                severity="info",
                details={"mode": "cpu", "expected_regex": gpu_regex},
            )
        device_name = torch.cuda.get_device_name(0)
        if re.search(gpu_regex, device_name):
            return PreflightResult(
                "gpu_name_matches", True,
                f"GPU '{device_name}' matches profile regex '{gpu_regex}'",
                severity="info",
                details={"device_name": device_name, "regex": gpu_regex},
            )
        else:
            return PreflightResult(
                "gpu_name_matches", False,
                f"GPU '{device_name}' does NOT match profile regex '{gpu_regex}'",
                severity="blocker",
                details={"device_name": device_name, "regex": gpu_regex},
            )
    except ImportError:
        return PreflightResult(
            "gpu_name_matches", False,
            "Cannot check: PyTorch not installed",
            severity="blocker",
        )


def check_nvml_available() -> PreflightResult:
    """Check if NVML telemetry is accessible."""
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        pynvml.nvmlShutdown()
        total_mb = mem_info.total / (1024**2)
        return PreflightResult(
            "nvml_available", True,
            f"NVML operational (total VRAM: {total_mb:.0f} MB)",
            severity="info",
            details={"total_vram_mb": round(total_mb)},
        )
    except ImportError:
        return PreflightResult(
            "nvml_available", False,
            "pynvml not installed (install with: pip install pynvml)",
            severity="warning",
            details={"hint": "pip install pynvml"},
        )
    except Exception as e:
        return PreflightResult(
            "nvml_available", False,
            f"NVML error: {str(e)[:100]}",
            severity="warning",
            details={"error": str(e)[:200]},
        )


def check_no_competing_gpu_processes() -> PreflightResult:
    """Check that no competing process is using the GPU."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=pid,name,used_memory",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return PreflightResult(
                "no_competing_gpu_processes", True,
                "Cannot query GPU processes (nvidia-smi unavailable)",
                severity="info",
            )
        output = result.stdout.strip()
        if not output or output.lower().startswith("no running"):
            return PreflightResult(
                "no_competing_gpu_processes", True,
                "No competing GPU processes detected",
                severity="info",
                details={"processes": []},
            )
        # Parse processes
        lines = [l.strip() for l in output.split("\n") if l.strip()]
        return PreflightResult(
            "no_competing_gpu_processes", False,
            f"{len(lines)} competing GPU process(es) detected",
            severity="warning",
            details={"processes": lines},
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return PreflightResult(
            "no_competing_gpu_processes", True,
            "nvidia-smi not available (skipped on this platform)",
            severity="info",
        )


# ===========================================================================
# Runbook generation
# ===========================================================================

def run_preflight() -> dict[str, Any]:
    """Run all preflight checks and return structured results."""
    checks = [
        check_torch_installed(),
        check_nvidia_driver(),
        check_cuda_available(),
        check_gpu_name_matches(),
        check_cuda_torch_compatibility(),
        check_vram_sufficient(),
        check_nvml_available(),
        check_no_competing_gpu_processes(),
        check_torch_device_config(),
        check_model_loadable(),
    ]

    blockers = [c for c in checks if not c.passed and c.severity == "blocker"]
    warnings = [c for c in checks if not c.passed and c.severity == "warning"]
    passed = [c for c in checks if c.passed]

    # Determine recommended device
    cuda_check = next((c for c in checks if c.name == "cuda_available"), None)
    compat_check = next((c for c in checks if c.name == "cuda_torch_compat"), None)
    vram_check = next((c for c in checks if c.name == "vram_sufficient"), None)

    if (cuda_check and cuda_check.passed
            and compat_check and compat_check.passed
            and vram_check and vram_check.passed):
        recommended_device = "cuda"
    else:
        recommended_device = "cpu"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "recommended_device": recommended_device,
        "gpu_ready": recommended_device == "cuda",
        "total_checks": len(checks),
        "passed": len(passed),
        "blockers": len(blockers),
        "warnings": len(warnings),
        "checks": [c.to_dict() for c in checks],
        "blocker_messages": [c.message for c in blockers],
        "warning_messages": [c.message for c in warnings],
    }


def generate_runbook(preflight: dict) -> str:
    """Generate GPU runbook markdown based on preflight results."""
    lines = [
        "# GPU Runbook — TraceAI LADC 2026",
        "",
        f"**Generated:** {preflight['timestamp']}",
        f"**Recommended Device:** `{preflight['recommended_device']}`",
        f"**GPU Ready:** {'✓ Yes' if preflight['gpu_ready'] else '✗ No'}",
        "",
        "## Preflight Results",
        "",
        f"| Check | Status | Message |",
        f"|-------|--------|---------|",
    ]

    for c in preflight["checks"]:
        status = "✓" if c["passed"] else ("✗" if c["severity"] == "blocker" else "⚠")
        lines.append(f"| {c['name']} | {status} | {c['message']} |")

    lines.extend([
        "",
        "## Device Selection Logic",
        "",
        "TraceAI uses automatic device detection (`device: auto` in config):",
        "",
        "```python",
        "# In src/traceai/service/inference.py",
        "if self._device_config == 'auto':",
        "    self._device_resolved = 'cuda' if torch.cuda.is_available() else 'cpu'",
        "```",
        "",
        "Override via environment: `$env:TRACEAI_DEVICE = 'cuda'` or `'cpu'`",
        "",
        "## Transitioning to GPU",
        "",
        "### Prerequisites",
        "",
        "1. NVIDIA GPU with Compute Capability >= 3.7",
        "2. NVIDIA driver installed (verify with `nvidia-smi`)",
        "3. PyTorch with CUDA support matching your driver",
        "",
        "### Install PyTorch with CUDA (if not already)",
        "",
        "```powershell",
        "# Detect installed CUDA version from driver",
        "nvidia-smi  # Look for 'CUDA Version: X.Y'",
        "",
        "# Select correct wheel from https://pytorch.org/get-started/locally/",
        "pip install torch --index-url https://download.pytorch.org/whl/<cuXXX>",
        "",
        "# Verify",
        'python -c "import torch; print(torch.cuda.is_available())"',
        "```",
        "",
        "**Do NOT hard-code a specific CUDA wheel version.** Always match",
        "your installed NVIDIA driver's CUDA capability.",
        "",
        "### Validation",
        "",
        "```powershell",
        "# Run preflight checks",
        "python scripts/phase5_gpu_runbook.py",
        "",
        "# Or run the doctor command",
        ".\\tasks.ps1 doctor -Profile local",
        "```",
        "",
        "### Expected Performance Difference",
        "",
        "| Metric | CPU (baseline) | GPU (expected) |",
        "|--------|---------------|----------------|",
        "| Model load time | ~90s | ~15s |",
        "| C0 P50 (50 tokens) | ~1000ms | ~100ms |",
        "| C1 P50 (20 tokens) | ~350ms | ~50ms |",
        "| Throughput | ~20 tok/s | ~200 tok/s |",
        "",
        "## Troubleshooting",
        "",
        "### 'No kernel image available'",
        "Your PyTorch CUDA version doesn't match your GPU. Reinstall PyTorch",
        "with the correct CUDA version for your driver.",
        "",
        "### Out of Memory",
        "GPT-2 (124M params) needs ~500MB VRAM. If VRAM < 2GB free,",
        "close other GPU applications first.",
        "",
        "### CPU fallback",
        "If GPU is unavailable, TraceAI automatically falls back to CPU.",
        "All experiments produce valid results on either device.",
        "GPU experiments simply run faster.",
    ])

    if preflight["blockers"] > 0:
        lines.extend([
            "",
            "## Current Blockers",
            "",
        ])
        for msg in preflight["blocker_messages"]:
            lines.append(f"- ✗ {msg}")

    if preflight["warnings"] > 0:
        lines.extend([
            "",
            "## Current Warnings",
            "",
        ])
        for msg in preflight["warning_messages"]:
            lines.append(f"- ⚠ {msg}")

    return "\n".join(lines)


def main() -> int:
    ts_start = time.perf_counter()
    print("[Phase 5] GPU Runbook — Environment Detection & Preflight")
    print(f"[Phase 5] Start: {datetime.now(timezone.utc).isoformat()}")

    # Run preflight
    preflight = run_preflight()

    # Print summary
    print(f"\n[Phase 5] Preflight: {preflight['passed']}/{preflight['total_checks']} passed")
    print(f"[Phase 5] Recommended device: {preflight['recommended_device']}")
    if preflight["blocker_messages"]:
        print("[Phase 5] Blockers:")
        for msg in preflight["blocker_messages"]:
            print(f"  [X] {msg}")
    if preflight["warning_messages"]:
        print("[Phase 5] Warnings:")
        for msg in preflight["warning_messages"]:
            print(f"  [!] {msg}")

    # Save outputs
    (OUT_DIR / "preflight_results.json").write_text(
        json.dumps(preflight, indent=2), encoding="utf-8"
    )

    runbook_md = generate_runbook(preflight)
    (OUT_DIR / "gpu_runbook.md").write_text(runbook_md, encoding="utf-8")

    # Generate LaTeX environment table
    generate_preflight_tex(preflight)

    elapsed = time.perf_counter() - ts_start
    print(f"\n[Phase 5] Complete. Duration: {elapsed:.1f}s")
    print(f"[Phase 5] Outputs: {OUT_DIR}")
    return 0


def generate_preflight_tex(preflight: dict) -> None:
    """Generate LaTeX table for preflight results."""
    lines = [
        r"\begin{table}[htbp]",
        r"\caption{GPU Preflight Validation Results}",
        r"\label{tab:gpu-preflight}",
        r"\centering\small",
        r"\begin{tabular}{llp{6cm}}",
        r"\toprule",
        r"\textbf{Check} & \textbf{Status} & \textbf{Details} \\",
        r"\midrule",
    ]

    for c in preflight["checks"]:
        status = r"\checkmark" if c["passed"] else r"\texttimes"
        # Escape underscores for LaTeX
        name = c["name"].replace("_", r"\_")
        msg = c["message"][:60].replace("_", r"\_").replace("%", r"\%")
        lines.append(f"  {name} & {status} & {msg} \\\\")

    lines.extend([
        r"\midrule",
        f"  \\textbf{{Recommended}} & \\multicolumn{{2}}{{l}}"
        f"{{\\texttt{{{preflight['recommended_device']}}}}} \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])
    (OUT_DIR / "gpu_preflight_table.tex").write_text(
        "\n".join(lines), encoding="utf-8"
    )


if __name__ == "__main__":
    sys.exit(main())
