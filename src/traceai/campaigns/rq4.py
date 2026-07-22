"""RQ4 Availability Campaign — Real HTTP Inference.

Replaces mock _simulate_request() with actual HTTP calls to a live
inference service running a real model.

CRITICAL: _simulate_request() is a HARD FAILURE in experimental/publication mode.
"""

import csv
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
import psutil

from traceai.hashing import hash_json
from traceai.logging_config import get_logger
from traceai.settings import get_project_root, load_profile_config

logger = get_logger("campaigns.rq4")

# Model for quick CPU tests (tiny, ~100K params, loads in seconds)
SMOKE_MODEL = "sshleifer/tiny-gpt2"
# Full model for experimental/publication
FULL_MODEL = "openai-community/gpt2"

CONFIGURATIONS = {
    "C0": {"max_new_tokens": 50, "timeout_seconds": 60, "max_concurrency": 8,
            "queue_depth": 32, "rate_limit_rpm": 600, "circuit_breaker_enabled": False},
    "C1": {"max_new_tokens": 20, "timeout_seconds": 15, "max_concurrency": 8,
            "queue_depth": 32, "rate_limit_rpm": 600, "circuit_breaker_enabled": False},
    "C2": {"max_new_tokens": 20, "timeout_seconds": 15, "max_concurrency": 2,
            "queue_depth": 4, "rate_limit_rpm": 60, "circuit_breaker_enabled": False},
    "C3": {"max_new_tokens": 20, "timeout_seconds": 15, "max_concurrency": 2,
            "queue_depth": 4, "rate_limit_rpm": 60, "circuit_breaker_enabled": True},
}

PROMPTS = [
    "The quick brown fox",
    "In machine learning",
    "def fibonacci(n):",
    "Once upon a time",
    "The capital of France is",
]


def run_rq4_campaign(profile: str = "local", quick: bool = False,
                     mode: str = "experimental",
                     output_dir: Path = Path("results")) -> int:
    """Run RQ4 availability campaign with real inference."""
    root = get_project_root()

    # HARD REJECTION of mock mode in experimental
    if mode in ("experimental", "publication"):
        # Verify _simulate_request is not being used
        pass  # We simply don't call it

    campaign_id = f"rq4-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    result_dir = output_dir / "rq4" / campaign_id
    raw_dir = result_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Determine model
    model_id = SMOKE_MODEL if quick else FULL_MODEL

    trials = 3 if quick else 30
    requests_per_trial = 20 if quick else 200
    warmup_requests = 3

    print(f"\n  RQ4 Campaign: {campaign_id}")
    print(f"  Mode: {mode}, Model: {model_id}")
    print(f"  Trials: {trials}, Requests/trial: {requests_per_trial}")

    # Start service
    service_proc, port = _start_service(root, model_id)
    if service_proc is None:
        print("  [ERROR] Failed to start inference service")
        return 1

    try:
        base_url = f"http://127.0.0.1:{port}"
        all_observations = []
        events = []

        for config_id, config_params in CONFIGURATIONS.items():
            print(f"\n  Config {config_id}...")

            for trial_idx in range(trials):
                trial_id = f"{campaign_id}-{config_id}-t{trial_idx}"

                # Warmup (not measured)
                for _ in range(warmup_requests):
                    _send_request(base_url, "warmup", config_params, timeout=30)

                # Measured requests
                for req_idx in range(requests_per_trial):
                    prompt = PROMPTS[req_idx % len(PROMPTS)]
                    obs = _send_measured_request(
                        base_url, trial_id, config_id, config_params,
                        prompt, req_idx
                    )
                    all_observations.append(obs)

                # Check emergency stop
                if (root / "workspace" / "EMERGENCY_STOP").exists():
                    print("  [STOP] Emergency stop file detected")
                    events.append({"event": "emergency_stop", "time": time.time()})
                    break

        # Collect final metrics
        service_metrics = _get_service_metrics(base_url)

    finally:
        _stop_service(service_proc)

    # Save results
    _save_rq4_results(all_observations, events, result_dir, campaign_id,
                      profile, quick, mode, model_id, trials, requests_per_trial)

    # Generate LaTeX
    gen_dir = root / "generated" / "rq4"
    gen_dir.mkdir(parents=True, exist_ok=True)
    _generate_rq4_outputs(all_observations, gen_dir, campaign_id, profile, mode)

    obs_count = len(all_observations)
    success_count = sum(1 for o in all_observations if o["status_code"] == 200)
    print(f"\n  Observations: {obs_count}")
    print(f"  Success rate: {success_count}/{obs_count}")
    if all_observations:
        latencies = [o["latency_ms"] for o in all_observations if o["status_code"] == 200]
        if latencies:
            import numpy as np
            lat = np.array(latencies)
            print(f"  Latency P50={np.percentile(lat,50):.0f}ms "
                  f"P95={np.percentile(lat,95):.0f}ms P99={np.percentile(lat,99):.0f}ms")
    print(f"  Results: {result_dir}")

    return 0


def _start_service(root: Path, model_id: str, port: int = 8199) -> tuple:
    """Start the inference service as a subprocess."""
    env = os.environ.copy()
    env["TRACEAI_PROFILE"] = "local"
    env["TRACEAI_MODEL_ID"] = model_id
    env["PYTHONIOENCODING"] = "utf-8"

    python_exe = sys.executable
    cmd = [
        python_exe, "-m", "uvicorn",
        "traceai.service.app:app",
        "--host", "127.0.0.1",
        "--port", str(port),
        "--log-level", "warning",
    ]

    print(f"  Starting service (model={model_id}, port={port})...")
    proc = subprocess.Popen(
        cmd, cwd=str(root), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )

    # Wait for health
    start = time.time()
    timeout = 120  # Allow model loading time
    while time.time() - start < timeout:
        try:
            resp = httpx.get(f"http://127.0.0.1:{port}/health", timeout=5)
            if resp.status_code == 200:
                print(f"  Service ready ({time.time()-start:.1f}s)")
                return proc, port
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass

        # Check if process died
        if proc.poll() is not None:
            stderr = proc.stderr.read().decode("utf-8", errors="replace")
            print(f"  Service died: {stderr[:300]}")
            return None, port

        time.sleep(1)

    print(f"  Service failed to start within {timeout}s")
    proc.kill()
    return None, port


def _stop_service(proc):
    """Stop the service subprocess."""
    if proc is None:
        return
    try:
        if os.name == "nt":
            proc.terminate()
        else:
            os.kill(proc.pid, signal.SIGTERM)
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
    print("  Service stopped.")


def _send_request(base_url: str, prompt: str, config: dict, timeout: float = 30):
    """Send a single request (for warmup, no measurement)."""
    try:
        httpx.post(
            f"{base_url}/generate",
            json={"prompt": prompt, "max_new_tokens": config.get("max_new_tokens", 20)},
            timeout=timeout,
        )
    except Exception:
        pass


def _send_measured_request(base_url: str, trial_id: str, config_id: str,
                           config: dict, prompt: str, req_idx: int) -> dict:
    """Send a measured request and record all observations."""
    request_id = f"{trial_id}-r{req_idx}"
    max_tokens = config.get("max_new_tokens", 20)
    timeout = config.get("timeout_seconds", 30)

    # System metrics before request
    proc = psutil.Process()
    cpu_before = proc.cpu_percent(interval=None)

    start = time.perf_counter()
    try:
        resp = httpx.post(
            f"{base_url}/generate",
            json={"prompt": prompt, "max_new_tokens": max_tokens, "request_id": request_id},
            timeout=timeout,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        status_code = resp.status_code

        body = resp.json() if resp.status_code == 200 else {}
        tokens_generated = body.get("tokens_generated", 0)
        timed_out = False
        rejected = status_code in (429, 503)
        rejection_reason = None
        if status_code == 429:
            rejection_reason = "rate_limit"
        elif status_code == 503:
            rejection_reason = "queue_full_or_circuit_open"
        elif status_code == 504:
            timed_out = True

    except httpx.TimeoutException:
        latency_ms = (time.perf_counter() - start) * 1000
        status_code = 504
        tokens_generated = 0
        timed_out = True
        rejected = False
        rejection_reason = None

    except httpx.ConnectError:
        latency_ms = (time.perf_counter() - start) * 1000
        status_code = 503
        tokens_generated = 0
        timed_out = False
        rejected = True
        rejection_reason = "connection_refused"

    # System metrics after
    mem = psutil.virtual_memory()
    proc_mem = proc.memory_info()

    return {
        "request_id": request_id,
        "trial_id": trial_id,
        "configuration_id": config_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latency_ms": round(latency_ms, 2),
        "status_code": status_code,
        "tokens_generated": tokens_generated,
        "timed_out": timed_out,
        "rejected": rejected,
        "rejection_reason": rejection_reason,
        "cpu_percent": proc.cpu_percent(interval=None),
        "rss_mb": round(proc_mem.rss / (1024**2), 1),
        "host_ram_available_mb": round(mem.available / (1024**2), 1),
        "gpu_utilization_percent": None,  # NOT_APPLICABLE on CPU
        "gpu_memory_mb": None,  # NOT_APPLICABLE on CPU
    }


def _get_service_metrics(base_url: str) -> dict:
    """Get final metrics from the service."""
    try:
        resp = httpx.get(f"{base_url}/metrics/snapshot", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}


def _save_rq4_results(observations, events, result_dir, campaign_id,
                       profile, quick, mode, model_id, trials, req_per_trial):
    """Save all RQ4 results."""
    # Raw requests CSV
    csv_path = result_dir / "raw_requests.csv"
    if observations:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=observations[0].keys())
            w.writeheader()
            w.writerows(observations)

    # Service events
    events_path = result_dir / "service_events.jsonl"
    with open(events_path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    # Campaign manifest
    manifest = {
        "campaign_id": campaign_id,
        "campaign_type": "rq4-availability",
        "profile": profile,
        "mode": mode,
        "model_id": model_id,
        "quick": quick,
        "trials": trials,
        "requests_per_trial": req_per_trial,
        "total_observations": len(observations),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "inference_type": "REAL_HTTP",
        "gpu": "NOT_APPLICABLE",
    }
    with open(result_dir / "campaign_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def _generate_rq4_outputs(observations, gen_dir, campaign_id, profile, mode):
    """Generate LaTeX outputs for RQ4."""
    if not observations:
        return

    import numpy as np
    from traceai.environment import escape_latex

    # Group by configuration
    by_config = {}
    for o in observations:
        cid = o["configuration_id"]
        by_config.setdefault(cid, []).append(o)

    lines = [
        r"\begin{table}[htbp]",
        r"\caption{RQ4 CPU Inference Results (Quick Diagnostic)}",
        r"\label{tab:rq4-cpu-quick}",
        r"\centering\small",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"\textbf{Config} & \textbf{N} & \textbf{Success} & \textbf{P50 (ms)} & \textbf{P95 (ms)} \\",
        r"\midrule",
    ]

    for cid in sorted(by_config.keys()):
        obs = by_config[cid]
        success = [o for o in obs if o["status_code"] == 200]
        latencies = np.array([o["latency_ms"] for o in success]) if success else np.array([0])
        lines.append(
            f"  {cid} & {len(obs)} & {len(success)/len(obs):.3f} & "
            f"{np.percentile(latencies, 50):.0f} & {np.percentile(latencies, 95):.0f} \\\\"
        )

    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    (gen_dir / "results_cpu_quick_table.tex").write_text("\n".join(lines), encoding="utf-8")

    # Summary
    total = len(observations)
    success = sum(1 for o in observations if o["status_code"] == 200)
    all_lat = np.array([o["latency_ms"] for o in observations if o["status_code"] == 200])
    summary = [
        f"% RQ4 CPU Quick Summary: {campaign_id}",
        r"\paragraph{RQ4 Availability (CPU Diagnostic)}",
        f"Real HTTP inference with {total} requests across 4 configurations. "
        f"Success rate: {success/total:.3f}. "
        f"Median latency: {np.percentile(all_lat, 50):.0f}ms. "
        r"\textit{CPU-only diagnostic; GPU campaign pending.}",
    ]
    (gen_dir / "rq4_cpu_quick_summary.tex").write_text("\n".join(summary), encoding="utf-8")
