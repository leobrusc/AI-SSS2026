"""Phase 4: RQ4 CPU Diagnostic — per-configuration outcome metrics.

Produces separate C0, C1, C2, C3 metrics with proper outcome classification:
  COMPLETED, EXPECTED_RATE_LIMIT, EXPECTED_QUEUE_REJECTION,
  EXPECTED_CIRCUIT_BREAKER, TIMEOUT, SERVER_ERROR, CLIENT_ERROR,
  EMERGENCY_ABORT.

Does NOT use a single aggregate success rate as the principal result.
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

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "generated" / "rq4" / "phase4_cpu_diagnostic"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SMOKE_MODEL = "sshleifer/tiny-gpt2"
SERVICE_PORT = 8199

CONFIGURATIONS = {
    "C0": {
        "max_new_tokens": 50, "timeout_seconds": 60, "max_concurrency": 8,
        "queue_depth": 32, "rate_limit_rpm": 600, "circuit_breaker_enabled": False,
        "description": "Baseline: generous limits, no circuit breaker",
    },
    "C1": {
        "max_new_tokens": 20, "timeout_seconds": 15, "max_concurrency": 8,
        "queue_depth": 32, "rate_limit_rpm": 600, "circuit_breaker_enabled": False,
        "description": "Reduced tokens + tighter timeout, high concurrency",
    },
    "C2": {
        "max_new_tokens": 20, "timeout_seconds": 15, "max_concurrency": 2,
        "queue_depth": 4, "rate_limit_rpm": 60, "circuit_breaker_enabled": False,
        "description": "Restricted concurrency + queue + rate limit",
    },
    "C3": {
        "max_new_tokens": 20, "timeout_seconds": 15, "max_concurrency": 2,
        "queue_depth": 4, "rate_limit_rpm": 60, "circuit_breaker_enabled": True,
        "description": "All controls active including circuit breaker",
    },
}

PROMPTS = [
    "The quick brown fox",
    "In machine learning",
    "def fibonacci(n):",
    "Once upon a time",
    "The capital of France is",
]

# Outcome classification
OUTCOME_COMPLETED = "COMPLETED"
OUTCOME_RATE_LIMIT = "EXPECTED_RATE_LIMIT"
OUTCOME_QUEUE_REJECT = "EXPECTED_QUEUE_REJECTION"
OUTCOME_CIRCUIT_BREAKER = "EXPECTED_CIRCUIT_BREAKER"
OUTCOME_TIMEOUT = "TIMEOUT"
OUTCOME_SERVER_ERROR = "SERVER_ERROR"
OUTCOME_CLIENT_ERROR = "CLIENT_ERROR"
OUTCOME_EMERGENCY_ABORT = "EMERGENCY_ABORT"


def classify_outcome(status_code: int, timed_out: bool,
                     detail: str = "") -> str:
    """Classify a request outcome into evidence-supported categories."""
    if timed_out or status_code == 504:
        return OUTCOME_TIMEOUT
    if status_code == 200:
        return OUTCOME_COMPLETED
    if status_code == 429:
        return OUTCOME_RATE_LIMIT
    if status_code == 503:
        if "circuit" in detail.lower():
            return OUTCOME_CIRCUIT_BREAKER
        if "queue" in detail.lower() or "full" in detail.lower():
            return OUTCOME_QUEUE_REJECT
        return OUTCOME_SERVER_ERROR
    if 400 <= status_code < 500:
        return OUTCOME_CLIENT_ERROR
    if 500 <= status_code < 600:
        return OUTCOME_SERVER_ERROR
    return OUTCOME_SERVER_ERROR


def main() -> int:
    ts_start = datetime.now(timezone.utc)
    print(f"[Phase 4] Start: {ts_start.isoformat()}")
    print(f"[Phase 4] Model: {SMOKE_MODEL} (CPU diagnostic)")

    # Start the inference service
    proc, port = start_service()
    if proc is None:
        print("[Phase 4] ERROR: Failed to start inference service")
        return 1

    try:
        base_url = f"http://127.0.0.1:{port}"
        all_observations = []
        config_metrics = {}

        for config_id, config in CONFIGURATIONS.items():
            print(f"\n[Phase 4] Configuration {config_id}: {config['description']}")

            # Update service configuration
            updated = update_configuration(base_url, config)
            if not updated:
                print(f"  WARNING: Could not update config for {config_id}")

            # Small warmup
            for i in range(2):
                send_request(base_url, PROMPTS[i], config, timeout=30)

            # Measured requests
            observations = []
            requests_per_config = 20
            for idx in range(requests_per_config):
                prompt = PROMPTS[idx % len(PROMPTS)]
                obs = send_measured_request(
                    base_url, config_id, config, prompt, idx
                )
                observations.append(obs)
                all_observations.append(obs)

            # Compute per-config metrics
            metrics = compute_config_metrics(config_id, observations)
            config_metrics[config_id] = metrics
            print_config_summary(config_id, metrics)

    finally:
        stop_service(proc)

    # Generate outputs
    ts_end = datetime.now(timezone.utc)
    save_all_outputs(all_observations, config_metrics, ts_start, ts_end)

    print(f"\n[Phase 4] Complete. Duration: {(ts_end - ts_start).total_seconds():.1f}s")
    print(f"[Phase 4] Outputs: {OUT_DIR}")
    return 0


def start_service() -> tuple:
    """Start the inference service subprocess."""
    env = os.environ.copy()
    env["TRACEAI_PROFILE"] = "local"
    env["TRACEAI_MODEL_ID"] = SMOKE_MODEL
    env["PYTHONIOENCODING"] = "utf-8"

    python_exe = sys.executable
    cmd = [
        python_exe, "-m", "uvicorn",
        "traceai.service.app:app",
        "--host", "127.0.0.1",
        "--port", str(SERVICE_PORT),
        "--log-level", "warning",
    ]

    print(f"[Phase 4] CMD: {' '.join(cmd)}")
    ts = time.perf_counter()

    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    proc = subprocess.Popen(
        cmd, cwd=str(ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=creation_flags,
    )

    # Wait for health
    timeout = 120
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = httpx.get(
                f"http://127.0.0.1:{SERVICE_PORT}/health", timeout=5
            )
            if resp.status_code == 200:
                elapsed = time.perf_counter() - ts
                print(f"[Phase 4] Service ready in {elapsed:.1f}s (exit_code=running)")
                return proc, SERVICE_PORT
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass

        if proc.poll() is not None:
            stderr = proc.stderr.read().decode("utf-8", errors="replace")
            print(f"[Phase 4] Service died: {stderr[:500]}")
            return None, SERVICE_PORT

        time.sleep(1)

    print(f"[Phase 4] Service timeout ({timeout}s)")
    proc.kill()
    return None, SERVICE_PORT


def stop_service(proc):
    """Stop the service."""
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
    print("[Phase 4] Service stopped.")


def update_configuration(base_url: str, config: dict) -> bool:
    """Update the service configuration via API."""
    try:
        resp = httpx.put(
            f"{base_url}/configuration",
            json={
                "max_new_tokens": config["max_new_tokens"],
                "timeout_seconds": config["timeout_seconds"],
                "max_concurrency": config["max_concurrency"],
                "queue_depth": config["queue_depth"],
                "rate_limit_rpm": config["rate_limit_rpm"],
                "circuit_breaker_enabled": config["circuit_breaker_enabled"],
            },
            timeout=10,
        )
        return resp.status_code in (200, 204)
    except Exception:
        return False


def send_request(base_url: str, prompt: str, config: dict, timeout: float = 30):
    """Send a warmup request (not measured)."""
    try:
        httpx.post(
            f"{base_url}/generate",
            json={"prompt": prompt, "max_new_tokens": config.get("max_new_tokens", 20)},
            timeout=timeout,
        )
    except Exception:
        pass


def send_measured_request(base_url: str, config_id: str, config: dict,
                          prompt: str, req_idx: int) -> dict:
    """Send a measured request and classify the outcome."""
    request_id = f"phase4-{config_id}-r{req_idx}"
    max_tokens = config.get("max_new_tokens", 20)
    timeout = min(config.get("timeout_seconds", 30), 120)  # Never > 120s

    start = time.perf_counter()
    detail = ""
    try:
        resp = httpx.post(
            f"{base_url}/generate",
            json={
                "prompt": prompt,
                "max_new_tokens": max_tokens,
                "request_id": request_id,
            },
            timeout=timeout,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        status_code = resp.status_code
        timed_out = False

        if status_code == 200:
            body = resp.json()
            tokens_generated = body.get("tokens_generated", 0)
        else:
            tokens_generated = 0
            try:
                err_body = resp.json()
                detail = err_body.get("detail", "")
            except Exception:
                detail = resp.text[:200]

    except httpx.TimeoutException:
        latency_ms = (time.perf_counter() - start) * 1000
        status_code = 504
        tokens_generated = 0
        timed_out = True

    except httpx.ConnectError:
        latency_ms = (time.perf_counter() - start) * 1000
        status_code = 503
        tokens_generated = 0
        timed_out = False
        detail = "connection_refused"

    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        status_code = 500
        tokens_generated = 0
        timed_out = False
        detail = str(e)[:200]

    outcome = classify_outcome(status_code, timed_out, detail)

    return {
        "request_id": request_id,
        "configuration_id": config_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_prefix": prompt[:30],
        "latency_ms": round(latency_ms, 2),
        "status_code": status_code,
        "tokens_generated": tokens_generated,
        "timed_out": timed_out,
        "outcome": outcome,
        "detail": detail,
    }


def compute_config_metrics(config_id: str, observations: list[dict]) -> dict:
    """Compute per-configuration metrics with outcome breakdown."""
    n = len(observations)
    if n == 0:
        return {"config_id": config_id, "n": 0}

    # Outcome counts
    outcomes = {}
    for o in observations:
        oc = o["outcome"]
        outcomes[oc] = outcomes.get(oc, 0) + 1

    # Latency stats (completed only)
    completed = [o for o in observations if o["outcome"] == OUTCOME_COMPLETED]
    if completed:
        latencies = np.array([o["latency_ms"] for o in completed])
        lat_stats = {
            "p50_ms": round(float(np.percentile(latencies, 50)), 1),
            "p95_ms": round(float(np.percentile(latencies, 95)), 1),
            "p99_ms": round(float(np.percentile(latencies, 99)), 1),
            "mean_ms": round(float(np.mean(latencies)), 1),
            "std_ms": round(float(np.std(latencies)), 1),
            "min_ms": round(float(np.min(latencies)), 1),
            "max_ms": round(float(np.max(latencies)), 1),
        }
    else:
        lat_stats = {}

    # Token throughput
    total_tokens = sum(o["tokens_generated"] for o in completed)
    total_time_s = sum(o["latency_ms"] for o in completed) / 1000.0 if completed else 0
    tokens_per_sec = total_tokens / total_time_s if total_time_s > 0 else 0.0

    return {
        "config_id": config_id,
        "n_requests": n,
        "outcome_counts": outcomes,
        "completed_count": len(completed),
        "completed_rate": round(len(completed) / n, 4),
        "expected_rejections": (
            outcomes.get(OUTCOME_RATE_LIMIT, 0)
            + outcomes.get(OUTCOME_QUEUE_REJECT, 0)
            + outcomes.get(OUTCOME_CIRCUIT_BREAKER, 0)
        ),
        "unexpected_failures": (
            outcomes.get(OUTCOME_TIMEOUT, 0)
            + outcomes.get(OUTCOME_SERVER_ERROR, 0)
            + outcomes.get(OUTCOME_CLIENT_ERROR, 0)
        ),
        "latency_stats": lat_stats,
        "tokens_per_second": round(tokens_per_sec, 2),
        "total_tokens_generated": total_tokens,
    }


def print_config_summary(config_id: str, metrics: dict):
    """Print per-config summary."""
    n = metrics["n_requests"]
    comp = metrics["completed_count"]
    print(f"  {config_id}: {comp}/{n} completed "
          f"({metrics['completed_rate']:.2%})")
    oc = metrics.get("outcome_counts", {})
    for outcome, count in sorted(oc.items()):
        if count > 0:
            print(f"    {outcome}: {count}")
    lat = metrics.get("latency_stats", {})
    if lat:
        print(f"    Latency: P50={lat['p50_ms']:.0f}ms "
              f"P95={lat['p95_ms']:.0f}ms")


def save_all_outputs(observations: list[dict], config_metrics: dict,
                     ts_start, ts_end):
    """Save all Phase 4 outputs."""
    # Raw observations CSV
    if observations:
        csv_path = OUT_DIR / "raw_observations.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=observations[0].keys())
            w.writeheader()
            w.writerows(observations)

    # Per-config metrics JSON
    summary = {
        "phase": "Phase 4: RQ4 CPU Diagnostic",
        "timestamp_start": ts_start.isoformat(),
        "timestamp_end": ts_end.isoformat(),
        "model": SMOKE_MODEL,
        "device": "cpu",
        "total_requests": len(observations),
        "configurations": config_metrics,
    }
    (OUT_DIR / "rq4_cpu_diagnostic.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )

    # LaTeX table
    generate_latex_table(config_metrics)

    # Outcome classification reference
    ref = {
        OUTCOME_COMPLETED: "Request processed successfully",
        OUTCOME_RATE_LIMIT: "Rejected by rate limiter (429)",
        OUTCOME_QUEUE_REJECT: "Rejected because queue is full (503)",
        OUTCOME_CIRCUIT_BREAKER: "Rejected by open circuit breaker (503)",
        OUTCOME_TIMEOUT: "Request timed out (504 or client timeout)",
        OUTCOME_SERVER_ERROR: "Unexpected server error (5xx)",
        OUTCOME_CLIENT_ERROR: "Client error (4xx, not rate limit)",
        OUTCOME_EMERGENCY_ABORT: "Campaign aborted by operator",
    }
    (OUT_DIR / "outcome_classification.json").write_text(
        json.dumps(ref, indent=2), encoding="utf-8"
    )


def generate_latex_table(config_metrics: dict):
    """Generate LaTeX table with per-config outcome breakdown."""
    lines = [
        r"\begin{table}[htbp]",
        r"\caption{RQ4 CPU Diagnostic: Per-Configuration Outcome Breakdown}",
        r"\label{tab:rq4-phase4-cpu}",
        r"\centering\small",
        r"\begin{tabular}{lrrrrrrr}",
        r"\toprule",
        (r"\textbf{Config} & \textbf{N} & \textbf{OK} & "
         r"\textbf{RateLimit} & \textbf{QueueFull} & "
         r"\textbf{CircuitBr} & \textbf{Timeout} & "
         r"\textbf{P50 (ms)} \\"),
        r"\midrule",
    ]

    for cid in ["C0", "C1", "C2", "C3"]:
        m = config_metrics.get(cid, {})
        n = m.get("n_requests", 0)
        oc = m.get("outcome_counts", {})
        lat = m.get("latency_stats", {})
        p50 = f"{lat['p50_ms']:.0f}" if lat else "---"
        lines.append(
            f"  {cid} & {n} & "
            f"{oc.get(OUTCOME_COMPLETED, 0)} & "
            f"{oc.get(OUTCOME_RATE_LIMIT, 0)} & "
            f"{oc.get(OUTCOME_QUEUE_REJECT, 0)} & "
            f"{oc.get(OUTCOME_CIRCUIT_BREAKER, 0)} & "
            f"{oc.get(OUTCOME_TIMEOUT, 0)} & "
            f"{p50} \\\\"
        )

    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    (OUT_DIR / "rq4_cpu_diagnostic_table.tex").write_text(
        "\n".join(lines), encoding="utf-8"
    )


if __name__ == "__main__":
    sys.exit(main())
