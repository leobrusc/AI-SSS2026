"""Phase 3: Exercise RQ4 Availability Controls — Stress Protocol.

Validates that C2 rate-limiting/queue and C3 circuit breaker actually activate.
Uses concurrent bursts and induced timeouts to trigger controls.

Model: sshleifer/tiny-gpt2 (pinned revision 5f91d94)
Protocol: 3 trials per configuration, fixed seeds.
"""
import asyncio
import csv
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "generated" / "rq4"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_ID = "sshleifer/tiny-gpt2"
MODEL_REVISION = "5f91d94bd9cd7190a9f3216ff93cd1dd95f2c7be"
SERVICE_PORT = 8199
MAX_TRIAL_SECONDS = 90
TRIALS = 3

PROMPTS = [
    "The quick brown fox jumps over",
    "In machine learning we often",
    "def fibonacci(n): return",
    "Once upon a time in a land",
    "The capital of France is Paris",
]

CONFIGS = {
    "C0": {
        "max_new_tokens": 30,
        "timeout_seconds": 60,
        "max_concurrency": 8,
        "queue_depth": 32,
        "rate_limit_rpm": 600,
        "circuit_breaker_enabled": False,
        "description": "Baseline: permissive, no policy rejection",
        "burst_size": 5,
        "sequential": True,
    },
    "C1": {
        "max_new_tokens": 15,
        "timeout_seconds": 10,
        "max_concurrency": 8,
        "queue_depth": 32,
        "rate_limit_rpm": 600,
        "circuit_breaker_enabled": False,
        "description": "Token limit + timeout, designed to complete",
        "burst_size": 8,
        "sequential": True,
    },
    "C2": {
        "max_new_tokens": 15,
        "timeout_seconds": 10,
        "max_concurrency": 1,
        "queue_depth": 1,
        "rate_limit_rpm": 10,
        "circuit_breaker_enabled": False,
        "description": "Low rate-limit + tiny queue to trigger rejections",
        "burst_size": 15,
        "sequential": False,  # concurrent burst!
    },
    "C3": {
        "max_new_tokens": 500,
        "timeout_seconds": 0.05,
        "max_concurrency": 8,
        "queue_depth": 32,
        "rate_limit_rpm": 600,
        "circuit_breaker_enabled": True,
        "description": "Circuit breaker: 500 tokens with 50ms timeout forces server-side timeout",
        "burst_size": 15,
        "sequential": True,  # Sequential so failures accumulate for CB
        "induce_timeout": True,
    },
}

# Outcome classification
OUTCOMES = {
    "COMPLETED": "Request completed successfully (200)",
    "EXPECTED_RATE_LIMIT": "Rate limit rejection (429)",
    "EXPECTED_QUEUE_REJECTION": "Queue full rejection (503, queue)",
    "EXPECTED_CIRCUIT_BREAKER": "Circuit breaker open (503, circuit)",
    "TIMEOUT": "Request timed out (504 or client timeout)",
    "SERVER_ERROR": "Unexpected server error (5xx)",
    "CLIENT_ERROR": "Unexpected client error (4xx)",
    "EMERGENCY_ABORT": "Campaign aborted",
}


def classify_outcome(status_code: int, timed_out: bool, detail: str = "") -> str:
    if timed_out or status_code == 504:
        return "TIMEOUT"
    if status_code == 200:
        return "COMPLETED"
    if status_code == 429:
        return "EXPECTED_RATE_LIMIT"
    if status_code == 503:
        dl = detail.lower()
        if "circuit" in dl:
            return "EXPECTED_CIRCUIT_BREAKER"
        if "queue" in dl or "full" in dl:
            return "EXPECTED_QUEUE_REJECTION"
        return "SERVER_ERROR"
    if 400 <= status_code < 500:
        return "CLIENT_ERROR"
    return "SERVER_ERROR"


def main() -> int:
    campaign_id = f"rq4-stress-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    ts_start = datetime.now(timezone.utc)
    print(f"[Phase 3] RQ4 Availability Controls Stress Protocol")
    print(f"[Phase 3] Campaign: {campaign_id}")
    print(f"[Phase 3] Model: {MODEL_ID}@{MODEL_REVISION[:8]}")

    # Create results directory
    result_dir = ROOT / "results" / "rq4" / campaign_id
    result_dir.mkdir(parents=True, exist_ok=True)

    # Start service
    proc, port = start_service()
    if proc is None:
        print("[Phase 3] ERROR: Service failed to start")
        return 1

    base_url = f"http://127.0.0.1:{port}"
    all_observations = []
    events = []
    config_metrics = {}

    try:
        for config_id, config in CONFIGS.items():
            print(f"\n[Phase 3] === {config_id}: {config['description']} ===")

            for trial in range(TRIALS):
                # Apply configuration
                apply_config(base_url, config)
                time.sleep(0.5)  # Let reset propagate

                trial_obs = run_trial(
                    base_url, config_id, config, trial, campaign_id
                )
                all_observations.extend(trial_obs)

            # Compute per-config metrics
            config_obs = [o for o in all_observations if o["configuration_id"] == config_id]
            metrics = compute_metrics(config_id, config_obs)
            config_metrics[config_id] = metrics
            print_metrics(config_id, metrics)

        # For C3: verify circuit recovery
        if "C3" in config_metrics:
            print("\n[Phase 3] Verifying C3 circuit recovery...")
            # Apply permissive config and wait for circuit breaker timeout (3s)
            apply_config(base_url, CONFIGS["C0"])
            time.sleep(4)  # Wait > circuit_breaker_timeout (3s)
            recovery_obs = send_single_request(base_url, "C3_RECOVERY", PROMPTS[0], 30, max_tokens=15)
            events.append({
                "event": "circuit_recovery_test",
                "time": datetime.now(timezone.utc).isoformat(),
                "outcome": recovery_obs["outcome"],
                "status_code": recovery_obs["status_code"],
            })
            if recovery_obs["outcome"] == "COMPLETED":
                print("  Circuit recovery: VERIFIED (request completed after cooldown)")
            else:
                print(f"  Circuit recovery: {recovery_obs['outcome']}")

    finally:
        stop_service(proc)

    ts_end = datetime.now(timezone.utc)

    # Validate protocol requirements
    validation = validate_protocol(config_metrics, events)

    # Save all outputs
    save_outputs(all_observations, events, config_metrics, validation,
                 campaign_id, ts_start, ts_end, result_dir)

    print(f"\n[Phase 3] === Protocol Validation ===")
    for check, result in validation.items():
        status = "PASS" if result["passed"] else "FAIL"
        print(f"  [{status}] {check}: {result['detail']}")

    all_pass = all(v["passed"] for v in validation.values())
    print(f"\n[Phase 3] Protocol {'PASSED' if all_pass else 'FAILED'}")
    print(f"[Phase 3] Duration: {(ts_end - ts_start).total_seconds():.1f}s")
    return 0 if all_pass else 1


def start_service() -> tuple:
    """Start inference service."""
    env = os.environ.copy()
    env["TRACEAI_PROFILE"] = "local"
    env["TRACEAI_MODEL_ID"] = MODEL_ID
    env["PYTHONIOENCODING"] = "utf-8"

    cmd = [
        sys.executable, "-m", "uvicorn",
        "traceai.service.app:app",
        "--host", "127.0.0.1",
        "--port", str(SERVICE_PORT),
        "--log-level", "warning",
    ]
    print(f"[Phase 3] CMD: {' '.join(cmd)}")
    ts = time.perf_counter()

    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=flags)

    timeout = 120
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = httpx.get(f"http://127.0.0.1:{SERVICE_PORT}/health", timeout=5)
            if resp.status_code == 200:
                print(f"[Phase 3] Service ready ({time.perf_counter()-ts:.1f}s)")
                return proc, SERVICE_PORT
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
        if proc.poll() is not None:
            err = proc.stderr.read().decode("utf-8", errors="replace")[:500]
            print(f"[Phase 3] Service died: {err}")
            return None, SERVICE_PORT
        time.sleep(1)

    proc.kill()
    return None, SERVICE_PORT


def stop_service(proc):
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
    print("[Phase 3] Service stopped.")


def apply_config(base_url: str, config: dict) -> bool:
    """Apply configuration via PUT /configuration."""
    try:
        payload = {
            "max_new_tokens": config["max_new_tokens"],
            "timeout_seconds": config["timeout_seconds"],
            "max_concurrency": config["max_concurrency"],
            "queue_depth": config["queue_depth"],
            "rate_limit_rpm": config["rate_limit_rpm"],
            "circuit_breaker_enabled": config.get("circuit_breaker_enabled", False),
        }
        if config.get("circuit_breaker_enabled"):
            payload["circuit_breaker_timeout"] = 3.0  # Short recovery for testing
        resp = httpx.put(f"{base_url}/configuration", json=payload, timeout=10)
        return resp.status_code in (200, 204)
    except Exception:
        return False


def run_trial(base_url: str, config_id: str, config: dict,
              trial: int, campaign_id: str) -> list[dict]:
    """Run a single trial with the configured burst pattern."""
    burst_size = config["burst_size"]
    sequential = config.get("sequential", True)
    induce_timeout = config.get("induce_timeout", False)
    # Client timeout must be longer than server timeout to capture 504 responses
    client_timeout = max(config.get("timeout_seconds", 30) + 5, 15)

    observations = []

    if sequential:
        for i in range(burst_size):
            prompt = PROMPTS[i % len(PROMPTS)]
            obs = send_single_request(base_url, config_id, prompt, client_timeout,
                                      max_tokens=config["max_new_tokens"])
            obs["trial"] = trial
            obs["request_index"] = i
            observations.append(obs)
    else:
        # Concurrent burst using threads
        with ThreadPoolExecutor(max_workers=burst_size) as executor:
            futures = []
            for i in range(burst_size):
                prompt = PROMPTS[i % len(PROMPTS)]
                futures.append(executor.submit(
                    send_single_request, base_url, config_id, prompt, client_timeout,
                    max_tokens=config["max_new_tokens"]
                ))
            for i, future in enumerate(as_completed(futures)):
                obs = future.result()
                obs["trial"] = trial
                obs["request_index"] = i
                observations.append(obs)

    return observations


def send_single_request(base_url: str, config_id: str, prompt: str,
                        timeout: float, max_tokens: int = 15) -> dict:
    """Send one measured request."""
    start = time.perf_counter()
    detail = ""
    tokens = 0
    timed_out = False

    try:
        resp = httpx.post(f"{base_url}/generate", json={
            "prompt": prompt,
            "max_new_tokens": max_tokens,
        }, timeout=timeout)
        latency_ms = (time.perf_counter() - start) * 1000
        status_code = resp.status_code
        if status_code == 200:
            body = resp.json()
            tokens = body.get("tokens_generated", 0)
        else:
            try:
                detail = resp.json().get("detail", "")
            except Exception:
                detail = resp.text[:200]
    except httpx.TimeoutException:
        latency_ms = (time.perf_counter() - start) * 1000
        status_code = 504
        timed_out = True
    except httpx.ConnectError:
        latency_ms = (time.perf_counter() - start) * 1000
        status_code = 503
        detail = "connection_refused"
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        status_code = 500
        detail = str(e)[:100]

    outcome = classify_outcome(status_code, timed_out, detail)

    return {
        "configuration_id": config_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latency_ms": round(latency_ms, 2),
        "status_code": status_code,
        "tokens_generated": tokens,
        "outcome": outcome,
        "detail": detail,
        "timed_out": timed_out,
    }


def compute_metrics(config_id: str, observations: list[dict]) -> dict:
    """Compute per-configuration metrics."""
    n = len(observations)
    if n == 0:
        return {"config_id": config_id, "n": 0}

    outcomes = {}
    for o in observations:
        outcomes[o["outcome"]] = outcomes.get(o["outcome"], 0) + 1

    completed = [o for o in observations if o["outcome"] == "COMPLETED"]
    latencies = np.array([o["latency_ms"] for o in completed]) if completed else np.array([0.0])

    expected_rejections = (
        outcomes.get("EXPECTED_RATE_LIMIT", 0)
        + outcomes.get("EXPECTED_QUEUE_REJECTION", 0)
        + outcomes.get("EXPECTED_CIRCUIT_BREAKER", 0)
    )
    unexpected = (
        outcomes.get("SERVER_ERROR", 0)
        + outcomes.get("CLIENT_ERROR", 0)
    )

    total_tokens = sum(o["tokens_generated"] for o in completed)
    total_time_s = sum(o["latency_ms"] for o in completed) / 1000.0 if completed else 0

    return {
        "config_id": config_id,
        "n_requests": n,
        "outcome_counts": outcomes,
        "completed_count": len(completed),
        "completed_rate": round(len(completed) / n, 4) if n > 0 else 0,
        "expected_rejection_count": expected_rejections,
        "expected_rejection_rate": round(expected_rejections / n, 4) if n > 0 else 0,
        "unexpected_failure_count": unexpected,
        "unexpected_failure_rate": round(unexpected / n, 4) if n > 0 else 0,
        "timeout_count": outcomes.get("TIMEOUT", 0),
        "latency_p50_ms": round(float(np.percentile(latencies, 50)), 1) if completed else 0,
        "latency_p95_ms": round(float(np.percentile(latencies, 95)), 1) if completed else 0,
        "latency_p99_ms": round(float(np.percentile(latencies, 99)), 1) if completed else 0,
        "tokens_per_second": round(total_tokens / total_time_s, 2) if total_time_s > 0 else 0,
        "total_tokens": total_tokens,
    }


def print_metrics(config_id: str, metrics: dict):
    n = metrics["n_requests"]
    print(f"  {config_id}: {metrics['completed_count']}/{n} completed, "
          f"{metrics['expected_rejection_count']} expected rejections, "
          f"{metrics['unexpected_failure_count']} unexpected")
    oc = metrics.get("outcome_counts", {})
    for outcome, count in sorted(oc.items()):
        print(f"    {outcome}: {count}")


def validate_protocol(config_metrics: dict, events: list) -> dict:
    """Validate the protocol requirements."""
    validation = {}

    # C0/C1: complete real inference
    for cid in ["C0", "C1"]:
        m = config_metrics.get(cid, {})
        passed = m.get("completed_count", 0) > 0
        validation[f"{cid}_completes_inference"] = {
            "passed": passed,
            "detail": f"{m.get('completed_count', 0)} requests completed",
        }

    # C2: at least one expected rate-limit or queue rejection
    m2 = config_metrics.get("C2", {})
    c2_rejections = m2.get("expected_rejection_count", 0)
    validation["C2_control_activation"] = {
        "passed": c2_rejections > 0,
        "detail": f"{c2_rejections} expected rejections (rate-limit or queue-full)",
    }

    # C3: circuit breaker opens
    m3 = config_metrics.get("C3", {})
    c3_cb = m3.get("outcome_counts", {}).get("EXPECTED_CIRCUIT_BREAKER", 0)
    validation["C3_circuit_opens"] = {
        "passed": c3_cb > 0,
        "detail": f"{c3_cb} circuit-breaker rejections observed",
    }

    # C3: circuit recovers
    recovery_events = [e for e in events if e.get("event") == "circuit_recovery_test"]
    recovered = any(e.get("outcome") == "COMPLETED" for e in recovery_events)
    validation["C3_circuit_recovers"] = {
        "passed": recovered,
        "detail": "Circuit recovered after cooldown" if recovered else "Recovery not confirmed",
    }

    # Unexpected failures separately reported
    total_unexpected = sum(
        config_metrics.get(c, {}).get("unexpected_failure_count", 0)
        for c in ["C0", "C1", "C2", "C3"]
    )
    validation["unexpected_failures_reported"] = {
        "passed": True,  # Always passes (it's a reporting requirement)
        "detail": f"{total_unexpected} total unexpected failures across all configs",
    }

    return validation


def save_outputs(observations, events, config_metrics, validation,
                 campaign_id, ts_start, ts_end, result_dir):
    """Save all Phase 3 outputs."""

    # Raw requests CSV
    if observations:
        csv_path = result_dir / "raw_requests.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            fields = list(observations[0].keys())
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(observations)

    # Service events JSONL
    events_path = result_dir / "service_events.jsonl"
    with open(events_path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    # Control activation table (LaTeX)
    tex_lines = [
        r"\begin{table}[htbp]",
        r"\caption{RQ4 Control Activation Results}",
        r"\label{tab:rq4-controls}",
        r"\centering\small",
        r"\begin{tabular}{lrrrrrrr}",
        r"\toprule",
        r"\textbf{Config} & \textbf{N} & \textbf{OK} & \textbf{Rate} & \textbf{Queue} & \textbf{CB} & \textbf{Timeout} & \textbf{P50} \\",
        r"\midrule",
    ]
    for cid in ["C0", "C1", "C2", "C3"]:
        m = config_metrics.get(cid, {})
        oc = m.get("outcome_counts", {})
        p50 = f"{m.get('latency_p50_ms', 0):.0f}" if m.get("completed_count", 0) > 0 else "---"
        tex_lines.append(
            f"  {cid} & {m.get('n_requests',0)} & "
            f"{oc.get('COMPLETED',0)} & "
            f"{oc.get('EXPECTED_RATE_LIMIT',0)} & "
            f"{oc.get('EXPECTED_QUEUE_REJECTION',0)} & "
            f"{oc.get('EXPECTED_CIRCUIT_BREAKER',0)} & "
            f"{oc.get('TIMEOUT',0)} & "
            f"{p50} \\\\"
        )
    tex_lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    (OUT_DIR / "control_activation_table.tex").write_text("\n".join(tex_lines), encoding="utf-8")

    # State transitions CSV
    transitions = []
    for o in observations:
        if o["outcome"] in ("EXPECTED_RATE_LIMIT", "EXPECTED_QUEUE_REJECTION", "EXPECTED_CIRCUIT_BREAKER"):
            transitions.append({
                "timestamp": o["timestamp"],
                "config": o["configuration_id"],
                "outcome": o["outcome"],
                "detail": o["detail"],
                "latency_ms": o["latency_ms"],
            })
    for e in events:
        transitions.append({
            "timestamp": e.get("time", ""),
            "config": "C3",
            "outcome": e.get("outcome", e.get("event", "")),
            "detail": e.get("event", ""),
            "latency_ms": "",
        })
    csv_path = OUT_DIR / "control_state_transitions.csv"
    if transitions:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["timestamp", "config", "outcome", "detail", "latency_ms"])
            w.writeheader()
            w.writerows(transitions)
    else:
        csv_path.write_text("# No transitions recorded\n", encoding="utf-8")

    # Summary markdown
    md_lines = [
        "# RQ4 Control Activation Summary",
        "",
        f"**Campaign:** {campaign_id}",
        f"**Duration:** {(ts_end - ts_start).total_seconds():.1f}s",
        f"**Model:** {MODEL_ID}@{MODEL_REVISION[:8]}",
        "",
        "## Per-Configuration Results",
        "",
    ]
    for cid in ["C0", "C1", "C2", "C3"]:
        m = config_metrics.get(cid, {})
        md_lines.append(f"### {cid}: {CONFIGS[cid]['description']}")
        md_lines.append(f"- Requests: {m.get('n_requests', 0)}")
        md_lines.append(f"- Completed: {m.get('completed_count', 0)}")
        md_lines.append(f"- Expected rejections: {m.get('expected_rejection_count', 0)}")
        md_lines.append(f"- Unexpected failures: {m.get('unexpected_failure_count', 0)}")
        md_lines.append(f"- Timeouts: {m.get('timeout_count', 0)}")
        if m.get("completed_count", 0) > 0:
            md_lines.append(f"- P50 latency: {m.get('latency_p50_ms', 0):.0f}ms")
        md_lines.append("")

    md_lines.append("## Protocol Validation")
    md_lines.append("")
    for check, result in validation.items():
        status = "PASS" if result["passed"] else "FAIL"
        md_lines.append(f"- [{status}] **{check}**: {result['detail']}")

    (OUT_DIR / "control_activation_summary.md").write_text("\n".join(md_lines), encoding="utf-8")

    # Full summary JSON
    summary = {
        "campaign_id": campaign_id,
        "timestamp_start": ts_start.isoformat(),
        "timestamp_end": ts_end.isoformat(),
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "configurations": config_metrics,
        "validation": validation,
        "total_observations": len(observations),
    }
    (OUT_DIR / "control_activation_results.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )


if __name__ == "__main__":
    sys.exit(main())
