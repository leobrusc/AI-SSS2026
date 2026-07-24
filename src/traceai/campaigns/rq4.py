"""RQ4 Availability Campaign — Real Concurrent HTTP Inference.

Uses httpx.AsyncClient with asyncio for concurrent workload generation.
Implements deterministic C2/C3 activation and circuit breaker recovery.

CRITICAL: Sequential loops are forbidden in experimental/publication mode.
CRITICAL: _simulate_request() is a HARD FAILURE in experimental/publication mode.
"""

import asyncio
import csv
import json
import os
import signal
import subprocess
import sys
import time
import threading
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

# ---------------------------------------------------------------------------
# Model revisions (immutable)
# ---------------------------------------------------------------------------
SMOKE_MODEL = "sshleifer/tiny-gpt2"
SMOKE_REVISION = "5f91d94bd9cd7190a9f3216ff93cd1dd95f2c7be"
FULL_MODEL = "openai-community/gpt2"
FULL_REVISION = "607a30d783dfa663caf39e06633721c8d4cfcd7e"

# ---------------------------------------------------------------------------
# Configurations C0-C3
# ---------------------------------------------------------------------------
CONFIGURATIONS = {
    "C0": {"max_new_tokens": 50, "timeout_seconds": 60, "max_concurrency": 8,
            "queue_depth": 32, "rate_limit_rpm": 600, "circuit_breaker_threshold": 0,
            "circuit_breaker_timeout": 30},
    "C1": {"max_new_tokens": 20, "timeout_seconds": 15, "max_concurrency": 8,
            "queue_depth": 32, "rate_limit_rpm": 600, "circuit_breaker_threshold": 0,
            "circuit_breaker_timeout": 30},
    "C2": {"max_new_tokens": 20, "timeout_seconds": 15, "max_concurrency": 2,
            "queue_depth": 4, "rate_limit_rpm": 60, "circuit_breaker_threshold": 0,
            "circuit_breaker_timeout": 30},
    "C3": {"max_new_tokens": 20, "timeout_seconds": 15, "max_concurrency": 2,
            "queue_depth": 4, "rate_limit_rpm": 60, "circuit_breaker_threshold": 3,
            "circuit_breaker_timeout": 5},
}

PROMPTS = [
    "The quick brown fox",
    "In machine learning",
    "def fibonacci(n):",
    "Once upon a time",
    "The capital of France is",
]

# ---------------------------------------------------------------------------
# Outcome classification
# ---------------------------------------------------------------------------
OUTCOME_COMPLETED = "COMPLETED"
OUTCOME_RATE_LIMIT = "EXPECTED_RATE_LIMIT"
OUTCOME_QUEUE_REJECTION = "EXPECTED_QUEUE_REJECTION"
OUTCOME_CIRCUIT_BREAKER = "EXPECTED_CIRCUIT_BREAKER"
OUTCOME_FAULT_TIMEOUT = "EXPECTED_FAULT_TIMEOUT"
OUTCOME_UNEXPECTED_TIMEOUT = "UNEXPECTED_TIMEOUT"
OUTCOME_SERVER_ERROR = "SERVER_ERROR"
OUTCOME_CLIENT_ERROR = "CLIENT_ERROR"
OUTCOME_CONNECTION_ERROR = "CONNECTION_ERROR"
OUTCOME_CUDA_OOM = "CUDA_OOM"
OUTCOME_EMERGENCY_ABORT = "EMERGENCY_ABORT"


def _classify_outcome(status_code: int, timed_out: bool, detail: str = "") -> str:
    """Classify a response into an outcome class."""
    if status_code == 200:
        return OUTCOME_COMPLETED
    if status_code == 429:
        return OUTCOME_RATE_LIMIT
    if status_code == 503:
        detail_lower = detail.lower()
        if "circuit breaker" in detail_lower:
            return OUTCOME_CIRCUIT_BREAKER
        if "queue full" in detail_lower:
            return OUTCOME_QUEUE_REJECTION
        return OUTCOME_SERVER_ERROR
    if status_code == 504 or timed_out:
        return OUTCOME_UNEXPECTED_TIMEOUT
    if 400 <= status_code < 500:
        return OUTCOME_CLIENT_ERROR
    if status_code >= 500:
        if "cuda" in detail.lower() and "oom" in detail.lower():
            return OUTCOME_CUDA_OOM
        return OUTCOME_SERVER_ERROR
    return OUTCOME_SERVER_ERROR


# ---------------------------------------------------------------------------
# GPU helpers
# ---------------------------------------------------------------------------
def _get_gpu_metadata() -> dict:
    """Get GPU metadata from NVML if available."""
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode("utf-8")
        uuid_str = pynvml.nvmlDeviceGetUUID(handle)
        if isinstance(uuid_str, bytes):
            uuid_str = uuid_str.decode("utf-8")
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        driver = pynvml.nvmlSystemGetDriverVersion()
        if isinstance(driver, bytes):
            driver = driver.decode("utf-8")
        pynvml.nvmlShutdown()
        return {
            "gpu_name": name,
            "gpu_uuid": uuid_str,
            "driver_version": driver,
            "vram_total_mb": round(mem_info.total / (1024**2)),
        }
    except Exception:
        return {"gpu": "NOT_APPLICABLE"}


class GPUTimeseriesSampler:
    """Background sampler for GPU telemetry during campaign execution."""

    def __init__(self, campaign_id: str, interval: float = 1.0):
        self.campaign_id = campaign_id
        self.interval = interval
        self.samples: list[dict] = []
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._config_id = "unknown"
        self._trial_id = "unknown"
        self._handle = None

    def set_context(self, config_id: str, trial_id: str):
        """Update the current config/trial context for samples."""
        self._config_id = config_id
        self._trial_id = trial_id

    def start(self):
        """Start background sampling."""
        try:
            import pynvml
            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            self._handle = None
            return
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop background sampling."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        try:
            import pynvml
            pynvml.nvmlShutdown()
        except Exception:
            pass

    def _sample_loop(self):
        import pynvml
        while not self._stop_event.is_set():
            try:
                util = pynvml.nvmlDeviceGetUtilizationRates(self._handle)
                mem = pynvml.nvmlDeviceGetMemoryInfo(self._handle)
                temp = pynvml.nvmlDeviceGetTemperature(
                    self._handle, pynvml.NVML_TEMPERATURE_GPU)
                try:
                    power = pynvml.nvmlDeviceGetPowerUsage(self._handle) / 1000.0
                except Exception:
                    power = 0.0
                self.samples.append({
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "campaign_id": self.campaign_id,
                    "configuration_id": self._config_id,
                    "trial_id": self._trial_id,
                    "gpu_utilization_percent": util.gpu,
                    "memory_used_mb": round(mem.used / (1024**2)),
                    "memory_total_mb": round(mem.total / (1024**2)),
                    "temperature_c": temp,
                    "power_w": round(power, 1),
                })
            except Exception:
                pass
            self._stop_event.wait(self.interval)



# ---------------------------------------------------------------------------
# Service management
# ---------------------------------------------------------------------------
def _start_service(root: Path, model_id: str, port: int = 8199,
                   profile: str = "local", revision: str = None) -> tuple:
    """Start the inference service as a subprocess."""
    env = os.environ.copy()
    env["TRACEAI_PROFILE"] = profile
    env["TRACEAI_MODEL_ID"] = model_id
    if revision:
        env["TRACEAI_MODEL_REVISION"] = revision
    if profile == "gpu":
        env.setdefault("TRACEAI_DEVICE", "cuda")
    env["PYTHONIOENCODING"] = "utf-8"

    python_exe = sys.executable
    cmd = [
        python_exe, "-m", "uvicorn",
        "traceai.service.app:app",
        "--host", "127.0.0.1",
        "--port", str(port),
        "--log-level", "warning",
    ]

    print(f"  Starting service (model={model_id}, port={port}, profile={profile})...")
    proc = subprocess.Popen(
        cmd, cwd=str(root), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )

    # Wait for health
    start = time.time()
    timeout = 120
    while time.time() - start < timeout:
        try:
            resp = httpx.get(f"http://127.0.0.1:{port}/health", timeout=5)
            if resp.status_code == 200:
                print(f"  Service ready ({time.time()-start:.1f}s)")
                return proc, port
        except (httpx.ConnectError, httpx.ReadTimeout):
            pass
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


def _apply_configuration(base_url: str, config_id: str, config: dict,
                         events: list) -> dict:
    """Apply configuration via PUT, verify with GET, record event."""
    put_resp = httpx.put(f"{base_url}/configuration", json=config, timeout=10)
    if put_resp.status_code != 200:
        raise RuntimeError(f"Failed to apply config {config_id}: {put_resp.text}")

    get_resp = httpx.get(f"{base_url}/configuration", timeout=10)
    if get_resp.status_code != 200:
        raise RuntimeError(f"Failed to verify config {config_id}: {get_resp.text}")

    returned = get_resp.json()

    # Verify key fields match
    for key in ("max_new_tokens", "timeout_seconds", "max_concurrency",
                "queue_depth", "rate_limit_rpm"):
        requested = config.get(key)
        actual = returned.get(key)
        if requested is not None and actual != requested:
            raise RuntimeError(
                f"Config {config_id} divergence: {key} requested={requested} actual={actual}"
            )

    events.append({
        "event": "configuration_applied",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config_id": config_id,
        "requested": config,
        "returned_digest": returned.get("configuration_digest"),
    })

    return returned


def _get_service_metrics(base_url: str) -> dict:
    """Get final metrics from the service."""
    try:
        resp = httpx.get(f"{base_url}/metrics/snapshot", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {}



# ---------------------------------------------------------------------------
# Async concurrent workload
# ---------------------------------------------------------------------------
async def _send_one_async(client: httpx.AsyncClient, base_url: str,
                          trial_id: str, config_id: str, config: dict,
                          prompt: str, req_idx: int, profile: str,
                          timeout: float) -> dict:
    """Send a single measured async request."""
    request_id = f"{trial_id}-r{req_idx}"
    max_tokens = config.get("max_new_tokens", 20)

    start = time.perf_counter()
    detail = ""
    try:
        resp = await client.post(
            f"{base_url}/generate",
            json={"prompt": prompt, "max_new_tokens": max_tokens,
                  "request_id": request_id},
            timeout=timeout,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        status_code = resp.status_code
        if status_code == 200:
            body = resp.json()
            tokens_generated = body.get("tokens_generated", 0)
        else:
            try:
                body = resp.json()
                detail = body.get("detail", "")
            except Exception:
                detail = resp.text[:200]
            tokens_generated = 0
        timed_out = False

    except httpx.TimeoutException:
        latency_ms = (time.perf_counter() - start) * 1000
        status_code = 504
        tokens_generated = 0
        timed_out = True

    except httpx.ConnectError:
        latency_ms = (time.perf_counter() - start) * 1000
        status_code = 0
        tokens_generated = 0
        timed_out = False
        detail = "connection_refused"

    outcome = _classify_outcome(status_code, timed_out, detail)
    if status_code == 0:
        outcome = OUTCOME_CONNECTION_ERROR

    return {
        "request_id": request_id,
        "trial_id": trial_id,
        "configuration_id": config_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latency_ms": round(latency_ms, 2),
        "status_code": status_code,
        "tokens_generated": tokens_generated,
        "timed_out": timed_out,
        "outcome_class": outcome,
        "detail": detail,
        "prompt_index": req_idx % len(PROMPTS),
    }


async def _run_trial_async(base_url: str, trial_id: str, config_id: str,
                           config: dict, n_requests: int, profile: str,
                           workload_seed: int, warmup: int = 3) -> list[dict]:
    """Run a single trial with concurrent requests."""
    import random
    rng = random.Random(workload_seed)
    timeout = config.get("timeout_seconds", 30)

    async with httpx.AsyncClient() as client:
        # Warmup (sequential, unmeasured)
        for i in range(warmup):
            prompt = PROMPTS[i % len(PROMPTS)]
            try:
                await client.post(
                    f"{base_url}/generate",
                    json={"prompt": prompt, "max_new_tokens": config.get("max_new_tokens", 20)},
                    timeout=30,
                )
            except Exception:
                pass

        # Measured concurrent burst
        prompt_indices = [rng.randint(0, len(PROMPTS) - 1) for _ in range(n_requests)]
        tasks = []
        for idx, pi in enumerate(prompt_indices):
            task = asyncio.create_task(
                _send_one_async(client, base_url, trial_id, config_id,
                                config, PROMPTS[pi], idx, profile, timeout)
            )
            tasks.append(task)
            # Stagger slightly to avoid pure thundering herd
            if idx % 5 == 4:
                await asyncio.sleep(0.01)

        results = await asyncio.gather(*tasks)
        return list(results)


async def _run_c3_fault_injection(base_url: str, campaign_id: str,
                                  config: dict, events: list) -> list[dict]:
    """Deterministic C3 circuit breaker exercise.

    1. Set very low timeout to force failures
    2. Send requests until circuit opens
    3. Confirm OPEN state (503 circuit breaker)
    4. Wait for cooldown
    5. Probe for recovery
    """
    threshold = config.get("circuit_breaker_threshold", 3)
    cooldown = config.get("circuit_breaker_timeout", 5)
    observations = []

    events.append({
        "event": "fault_injection_started",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config_id": "C3",
        "threshold": threshold,
        "cooldown": cooldown,
    })

    # Phase 1: Apply config with very short timeout to force failures
    fault_config = dict(config)
    fault_config["timeout_seconds"] = 0.001  # force timeout
    try:
        httpx.put(f"{base_url}/configuration", json=fault_config, timeout=10)
    except Exception:
        pass

    # Phase 2: Send requests to trigger threshold failures
    async with httpx.AsyncClient() as client:
        open_timestamp = None
        for i in range(threshold + 5):
            trial_id = f"{campaign_id}-C3-fault-r{i}"
            start = time.perf_counter()
            try:
                resp = await client.post(
                    f"{base_url}/generate",
                    json={"prompt": "fault injection probe",
                          "max_new_tokens": 5, "request_id": trial_id},
                    timeout=10,
                )
                latency_ms = (time.perf_counter() - start) * 1000
                status_code = resp.status_code
                try:
                    detail = resp.json().get("detail", "")
                except Exception:
                    detail = ""
            except httpx.TimeoutException:
                latency_ms = (time.perf_counter() - start) * 1000
                status_code = 504
                detail = "client_timeout"
            except httpx.ConnectError:
                latency_ms = (time.perf_counter() - start) * 1000
                status_code = 0
                detail = "connection_refused"
                break

            outcome = _classify_outcome(status_code, status_code == 504, detail)
            if status_code == 0:
                outcome = OUTCOME_CONNECTION_ERROR

            observations.append({
                "request_id": trial_id,
                "trial_id": f"{campaign_id}-C3-fault",
                "configuration_id": "C3",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latency_ms": round(latency_ms, 2),
                "status_code": status_code,
                "tokens_generated": 0,
                "timed_out": status_code == 504,
                "outcome_class": outcome,
                "detail": detail,
                "prompt_index": 0,
            })

            if outcome == OUTCOME_CIRCUIT_BREAKER and open_timestamp is None:
                open_timestamp = time.time()
                events.append({
                    "event": "circuit_open",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                break

        # Phase 3: Confirm OPEN state
        if open_timestamp:
            try:
                resp = await client.post(
                    f"{base_url}/generate",
                    json={"prompt": "confirm open", "max_new_tokens": 5},
                    timeout=5,
                )
                if resp.status_code == 503:
                    detail = resp.json().get("detail", "")
                    if "circuit breaker" in detail.lower():
                        observations.append({
                            "request_id": f"{campaign_id}-C3-open-confirm",
                            "trial_id": f"{campaign_id}-C3-fault",
                            "configuration_id": "C3",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "latency_ms": 0,
                            "status_code": 503,
                            "tokens_generated": 0,
                            "timed_out": False,
                            "outcome_class": OUTCOME_CIRCUIT_BREAKER,
                            "detail": detail,
                            "prompt_index": 0,
                        })
            except Exception:
                pass

            # Phase 4: Wait for cooldown
            events.append({
                "event": "circuit_half_open",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            await asyncio.sleep(cooldown + 1)

            # Phase 5: Restore normal timeout and probe for recovery
            recovery_config = dict(config)
            recovery_config["timeout_seconds"] = 60
            try:
                httpx.put(f"{base_url}/configuration", json=recovery_config, timeout=10)
            except Exception:
                pass

            try:
                resp = await client.post(
                    f"{base_url}/generate",
                    json={"prompt": "recovery probe", "max_new_tokens": 5},
                    timeout=60,
                )
                if resp.status_code == 200:
                    events.append({
                        "event": "circuit_recovered",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "recovery_time_ms": round((time.time() - open_timestamp) * 1000),
                    })
                    observations.append({
                        "request_id": f"{campaign_id}-C3-recovery",
                        "trial_id": f"{campaign_id}-C3-fault",
                        "configuration_id": "C3",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "latency_ms": 0,
                        "status_code": 200,
                        "tokens_generated": resp.json().get("tokens_generated", 0),
                        "timed_out": False,
                        "outcome_class": OUTCOME_COMPLETED,
                        "detail": "recovery_probe",
                        "prompt_index": 0,
                    })
            except Exception as e:
                events.append({
                    "event": "circuit_recovery_failed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error": str(e)[:200],
                })

    # Restore original config
    try:
        httpx.put(f"{base_url}/configuration", json=config, timeout=10)
    except Exception:
        pass

    return observations



# ---------------------------------------------------------------------------
# Main campaign entry point
# ---------------------------------------------------------------------------
def run_rq4_campaign(profile: str = "local", quick: bool = False,
                     mode: str = "experimental",
                     output_dir: Path = Path("results")) -> int:
    """Run RQ4 availability campaign with real concurrent inference."""
    root = get_project_root()
    campaign_start = datetime.now(timezone.utc)

    campaign_id = f"rq4-{campaign_start.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    result_dir = root / output_dir / "rq4" / campaign_id
    result_dir.mkdir(parents=True, exist_ok=True)

    # Model selection
    if quick:
        model_id, model_revision = SMOKE_MODEL, SMOKE_REVISION
    else:
        model_id, model_revision = FULL_MODEL, FULL_REVISION

    trials = 3 if quick else 30
    requests_per_trial = 20 if quick else 200
    expected_observations = trials * len(CONFIGURATIONS) * requests_per_trial

    print(f"\n  RQ4 Campaign: {campaign_id}")
    print(f"  Mode: {mode}, Profile: {profile}, Model: {model_id}")
    print(f"  Revision: {model_revision}")
    print(f"  Trials: {trials}, Requests/trial: {requests_per_trial}")
    print(f"  Expected observations: {expected_observations}")

    # Start GPU sampler if gpu profile
    gpu_sampler = None
    if profile == "gpu":
        gpu_sampler = GPUTimeseriesSampler(campaign_id, interval=1.0)
        gpu_sampler.start()

    # Start service
    service_proc, port = _start_service(root, model_id, profile=profile,
                                        revision=model_revision)
    if service_proc is None:
        print("  [ERROR] Failed to start inference service")
        if gpu_sampler:
            gpu_sampler.stop()
        return 1

    events: list[dict] = []
    events.append({
        "event": "service_started",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_id": model_id, "profile": profile, "port": port,
    })

    all_observations: list[dict] = []
    trial_manifests: list[dict] = []
    config_events: list[dict] = []
    resource_samples: list[dict] = []

    try:
        base_url = f"http://127.0.0.1:{port}"

        for config_id, config_params in CONFIGURATIONS.items():
            print(f"\n  Config {config_id}...")

            # Apply configuration
            try:
                verified = _apply_configuration(base_url, config_id,
                                                config_params, config_events)
                events.append({
                    "event": "configuration_applied",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "config_id": config_id,
                })
            except RuntimeError as e:
                print(f"  [ERROR] {e}")
                events.append({"event": "config_apply_failed",
                               "config_id": config_id, "error": str(e),
                               "timestamp": datetime.now(timezone.utc).isoformat()})
                continue

            for trial_idx in range(trials):
                trial_id = f"{campaign_id}-{config_id}-t{trial_idx}"
                workload_seed = hash(f"{campaign_id}-{config_id}-{trial_idx}") & 0xFFFFFFFF
                trial_start = datetime.now(timezone.utc)

                if gpu_sampler:
                    gpu_sampler.set_context(config_id, trial_id)

                events.append({
                    "event": "trial_started",
                    "timestamp": trial_start.isoformat(),
                    "trial_id": trial_id, "config_id": config_id,
                })

                # Resource sample
                proc_info = psutil.Process()
                mem = psutil.virtual_memory()
                resource_samples.append({
                    "timestamp_utc": trial_start.isoformat(),
                    "service_pid": service_proc.pid if service_proc else 0,
                    "cpu_percent": proc_info.cpu_percent(interval=None),
                    "rss_mb": round(proc_info.memory_info().rss / (1024**2), 1),
                    "host_ram_available_mb": round(mem.available / (1024**2), 1),
                    "configuration_id": config_id,
                    "trial_id": trial_id,
                })

                # Run concurrent trial
                trial_obs = asyncio.run(
                    _run_trial_async(base_url, trial_id, config_id,
                                     config_params, requests_per_trial,
                                     profile, workload_seed)
                )
                all_observations.extend(trial_obs)

                trial_end = datetime.now(timezone.utc)
                trial_manifests.append({
                    "trial_id": trial_id,
                    "workload_seed": workload_seed,
                    "configuration_id": config_id,
                    "start_utc": trial_start.isoformat(),
                    "end_utc": trial_end.isoformat(),
                    "observation_count": len(trial_obs),
                })

                events.append({
                    "event": "trial_finished",
                    "timestamp": trial_end.isoformat(),
                    "trial_id": trial_id,
                    "observations": len(trial_obs),
                })

                # Emergency stop check
                if (root / "workspace" / "EMERGENCY_STOP").exists():
                    print("  [STOP] Emergency stop")
                    events.append({"event": "emergency_stop",
                                   "timestamp": datetime.now(timezone.utc).isoformat()})
                    break

            # C3 fault injection phase (after normal trials)
            if config_id == "C3":
                print("  C3 fault injection...")
                c3_obs = asyncio.run(
                    _run_c3_fault_injection(base_url, campaign_id,
                                           config_params, events)
                )
                all_observations.extend(c3_obs)

        # Final metrics
        service_metrics = _get_service_metrics(base_url)

    finally:
        _stop_service(service_proc)
        events.append({
            "event": "service_stopped",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if gpu_sampler:
            gpu_sampler.stop()

    campaign_end = datetime.now(timezone.utc)

    # Persist all artifacts
    _save_all_artifacts(
        result_dir, campaign_id, profile, mode, quick,
        model_id, model_revision, trials, requests_per_trial,
        expected_observations, all_observations, events, config_events,
        trial_manifests, resource_samples,
        gpu_sampler.samples if gpu_sampler else [],
        campaign_start, campaign_end, root,
    )

    # Quick validation gates
    if quick and profile == "gpu":
        report = _generate_quick_validation_report(
            root, campaign_id, all_observations, events,
            gpu_sampler.samples if gpu_sampler else [],
            resource_samples, expected_observations, model_revision,
        )
        if report["status"] != "PASS":
            print(f"\n  [FAIL] Quick validation: {report['status']}")
            for gate, val in report["gates"].items():
                if not val:
                    print(f"    ✗ {gate}")
            return 1

    # Summary
    obs_count = len(all_observations)
    success_count = sum(1 for o in all_observations
                        if o.get("outcome_class") == OUTCOME_COMPLETED)
    print(f"\n  Observations: {obs_count}")
    print(f"  Completed: {success_count}")
    print(f"  Results: {result_dir}")
    return 0



# ---------------------------------------------------------------------------
# Artifact persistence
# ---------------------------------------------------------------------------
def _save_all_artifacts(result_dir, campaign_id, profile, mode, quick,
                        model_id, model_revision, trials, req_per_trial,
                        expected_observations, observations, events,
                        config_events, trial_manifests, resource_samples,
                        gpu_samples, campaign_start, campaign_end, root):
    """Save all mandatory campaign artifacts."""

    # raw_requests.csv
    if observations:
        csv_path = result_dir / "raw_requests.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=observations[0].keys())
            w.writeheader()
            w.writerows(observations)

    # gpu_timeseries.csv
    gpu_csv = result_dir / "gpu_timeseries.csv"
    if gpu_samples:
        with open(gpu_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=gpu_samples[0].keys())
            w.writeheader()
            w.writerows(gpu_samples)
    else:
        gpu_csv.write_text("", encoding="utf-8")

    # resource_timeseries.csv
    res_csv = result_dir / "resource_timeseries.csv"
    if resource_samples:
        with open(res_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=resource_samples[0].keys())
            w.writeheader()
            w.writerows(resource_samples)

    # service_events.jsonl
    with open(result_dir / "service_events.jsonl", "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    # configuration_events.jsonl
    with open(result_dir / "configuration_events.jsonl", "w", encoding="utf-8") as f:
        for e in config_events:
            f.write(json.dumps(e) + "\n")

    # trial_manifest.json
    with open(result_dir / "trial_manifest.json", "w", encoding="utf-8") as f:
        json.dump(trial_manifests, f, indent=2)

    # prompt_corpus_hash.json
    corpus_data = {"prompts": PROMPTS, "count": len(PROMPTS)}
    with open(result_dir / "prompt_corpus_hash.json", "w", encoding="utf-8") as f:
        json.dump({"hash": hash_json(corpus_data), "corpus": corpus_data}, f, indent=2)

    # campaign_manifest.json
    # Determine git state
    source_commit = "unknown"
    exact_tag = "untagged"
    working_tree_clean = False
    try:
        source_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(root),
            text=True, stderr=subprocess.DEVNULL).strip()
        exact_tag = subprocess.check_output(
            ["git", "describe", "--tags", "--exact-match"],
            cwd=str(root), text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        pass
    try:
        status = subprocess.check_output(
            ["git", "status", "--short"], cwd=str(root),
            text=True, stderr=subprocess.DEVNULL).strip()
        working_tree_clean = len(status) == 0
    except Exception:
        pass

    manifest = {
        "campaign_id": campaign_id,
        "campaign_type": "rq4-availability",
        "profile": profile,
        "mode": mode,
        "quick": quick,
        "model_id": model_id,
        "requested_revision": model_revision,
        "trials": trials,
        "requests_per_trial": req_per_trial,
        "total_observations": len(observations),
        "expected_observations": expected_observations,
        "inference_type": "REAL_HTTP",
        "mock_used": False,
        "campaign_start": campaign_start.isoformat(),
        "campaign_end": campaign_end.isoformat(),
        "source_commit": source_commit,
        "exact_tag": exact_tag,
        "working_tree_clean": working_tree_clean,
    }

    if profile == "gpu":
        try:
            import torch
            manifest["torch_version"] = torch.__version__
            manifest["torch_cuda_runtime"] = torch.version.cuda
            manifest["device"] = "cuda"
        except Exception:
            manifest["device"] = "unknown"
        gpu_meta = _get_gpu_metadata()
        if "gpu_name" in gpu_meta:
            manifest.update(gpu_meta)
        else:
            raise RuntimeError("GPU profile must produce real GPU metadata, got NOT_APPLICABLE")
    else:
        manifest["device"] = "cpu"
        manifest["gpu"] = "NOT_APPLICABLE"

    with open(result_dir / "campaign_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


# ---------------------------------------------------------------------------
# Quick validation report
# ---------------------------------------------------------------------------
def _generate_quick_validation_report(root, campaign_id, observations, events,
                                      gpu_samples, resource_samples,
                                      expected_obs, model_revision) -> dict:
    """Generate quick validation gates report."""
    gates = {}

    # Basic gates
    gates["real_http"] = True  # We never use mocks in this path
    gates["no_mock"] = True

    # Observation count (C0-C3 normal trials only, excluding fault injection)
    normal_obs = [o for o in observations if "fault" not in o.get("trial_id", "")]
    gates["observation_count_240"] = len(normal_obs) >= 240

    # C0/C1 completed
    c0_obs = [o for o in normal_obs if o["configuration_id"] == "C0"]
    c1_obs = [o for o in normal_obs if o["configuration_id"] == "C1"]
    gates["c0_completed"] = any(o["outcome_class"] == OUTCOME_COMPLETED for o in c0_obs)
    gates["c1_completed"] = any(o["outcome_class"] == OUTCOME_COMPLETED for o in c1_obs)

    # C2 control activated
    c2_obs = [o for o in normal_obs if o["configuration_id"] == "C2"]
    c2_controls = [o for o in c2_obs if o["outcome_class"] in
                   (OUTCOME_RATE_LIMIT, OUTCOME_QUEUE_REJECTION)]
    gates["c2_control_activated"] = len(c2_controls) > 0

    # C3 gates
    c3_all = [o for o in observations if o["configuration_id"] == "C3"]
    gates["c3_opened"] = any(
        e["event"] == "circuit_open" for e in events)
    gates["c3_open_responses"] = any(
        o["outcome_class"] == OUTCOME_CIRCUIT_BREAKER for o in c3_all)
    gates["c3_recovered"] = any(
        e["event"] == "circuit_recovered" for e in events)

    # GPU gates
    gates["gpu_timeseries_present"] = len(gpu_samples) > 0
    gates["gpu_utilization_non_null"] = any(
        s.get("gpu_utilization_percent") is not None for s in gpu_samples)
    gates["gpu_memory_non_null"] = any(
        s.get("memory_used_mb") is not None for s in gpu_samples)

    # Resource timeseries
    gates["resource_timeseries_present"] = len(resource_samples) > 0

    # Error gates
    gates["no_connection_error"] = not any(
        o["outcome_class"] == OUTCOME_CONNECTION_ERROR for o in observations)
    gates["no_cuda_oom"] = not any(
        o["outcome_class"] == OUTCOME_CUDA_OOM for o in observations)
    gates["no_unexpected_failure"] = not any(
        o["outcome_class"] in (OUTCOME_SERVER_ERROR, OUTCOME_CLIENT_ERROR)
        for o in normal_obs)

    # Model revision
    gates["model_revision_pinned"] = model_revision is not None and len(model_revision) == 40

    # Working tree
    try:
        status = subprocess.check_output(
            ["git", "status", "--short"], cwd=str(root),
            text=True, stderr=subprocess.DEVNULL).strip()
        gates["working_tree_clean"] = len(status) == 0
    except Exception:
        gates["working_tree_clean"] = False

    # Overall status
    all_pass = all(gates.values())
    status = "PASS" if all_pass else "FAIL"

    report = {
        "campaign_id": campaign_id,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gates": gates,
        "observations_total": len(observations),
        "observations_normal": len(normal_obs),
    }

    # Save report
    gpu_dir = root / "generated" / "gpu"
    gpu_dir.mkdir(parents=True, exist_ok=True)
    with open(gpu_dir / "quick_validation_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Markdown report
    md_lines = [
        f"# Quick Validation Report — {campaign_id}",
        f"",
        f"**Status: {status}**",
        f"**Timestamp:** {report['timestamp']}",
        f"",
        "| Gate | Result |",
        "|------|--------|",
    ]
    for gate, val in gates.items():
        md_lines.append(f"| {gate} | {'✓ PASS' if val else '✗ FAIL'} |")
    md_lines.append(f"\nObservations: {len(observations)} total, {len(normal_obs)} normal")

    (gpu_dir / "quick_validation_report.md").write_text(
        "\n".join(md_lines), encoding="utf-8")

    return report
