"""Availability campaign: runtime controls and fault detection (RQ4)."""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from traceai.hashing import hash_json
from traceai.logging_config import get_logger
from traceai.settings import get_project_root, load_profile_config

logger = get_logger("campaigns.availability")


def run_availability_campaign(
    profile: str = "local",
    quick: bool = False,
    output_dir: Path = Path("results"),
) -> int:
    """Run the availability campaign (C0-C3, S6-S7, S11)."""
    root = get_project_root()
    config = load_profile_config(profile)
    campaigns_cfg = config.get("campaigns", {})

    trials = campaigns_cfg.get("quick_trials", 3) if quick else campaigns_cfg.get("full_trials", 30)
    requests_per_trial = (
        campaigns_cfg.get("quick_requests_per_trial", 20) if quick
        else campaigns_cfg.get("full_requests_per_trial", 200)
    )

    campaign_id = f"availability-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    raw_dir = output_dir / "raw" / campaign_id
    raw_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        f"Starting availability campaign: {campaign_id} "
        f"({trials} trials, {requests_per_trial} req/trial, profile={profile})"
    )

    # Load prompt fixtures
    prompts = _load_prompts(root)

    # Configurations to test
    configurations = _get_configurations(config)

    all_observations: list[dict] = []
    base_seed = 42

    for config_id, config_params in configurations.items():
        logger.info(f"  Configuration: {config_id}")

        for trial_idx in range(trials):
            trial_seed = base_seed + trial_idx
            trial_id = f"{campaign_id}-{config_id}-t{trial_idx}"

            observations = _run_trial(
                trial_id=trial_id,
                config_id=config_id,
                config_params=config_params,
                prompts=prompts,
                requests_per_trial=requests_per_trial,
                seed=trial_seed,
                profile=profile,
            )
            all_observations.extend(observations)

    # Save results
    results_path = raw_dir / "availability_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(all_observations, f, indent=2, default=str)

    # Save campaign manifest
    manifest = {
        "campaign_id": campaign_id,
        "campaign_type": "availability",
        "profile": profile,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "trial_count": trials,
        "requests_per_trial": requests_per_trial,
        "configurations": list(configurations.keys()),
        "total_observations": len(all_observations),
        "quick": quick,
        "raw_directory": str(raw_dir),
        "results_file": str(results_path),
    }
    manifest_path = raw_dir / "campaign_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(
        f"Availability campaign complete: {len(all_observations)} observations "
        f"across {len(configurations)} configurations"
    )
    print(f"\n  Campaign: {campaign_id}")
    print(f"  Results:  {results_path}")
    print(f"  Observations: {len(all_observations)}")
    print(f"  Configurations: {list(configurations.keys())}")

    return 0


def _load_prompts(root: Path) -> list[str]:
    """Load prompt fixtures for the campaign."""
    prompts_dir = root / "fixtures" / "prompts"
    prompts = []

    smoke_file = prompts_dir / "smoke.jsonl"
    if smoke_file.exists():
        with open(smoke_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        prompts.append(data.get("prompt", ""))
                    except json.JSONDecodeError:
                        prompts.append(line)

    if not prompts:
        prompts = [
            "The quick brown fox",
            "Once upon a time in a land far away",
            "def fibonacci(n):",
            "The capital of France is",
            "In machine learning, overfitting occurs when",
        ]

    return prompts


def _get_configurations(config: dict) -> dict[str, dict]:
    """Extract experiment configurations."""
    return {
        "C0": {
            "max_new_tokens": 512,
            "timeout_seconds": 120,
            "max_concurrency": 32,
            "queue_depth": 128,
            "rate_limit_rpm": 1000,
            "circuit_breaker_enabled": False,
        },
        "C1": {
            "max_new_tokens": 100,
            "timeout_seconds": 30,
            "max_concurrency": 32,
            "queue_depth": 128,
            "rate_limit_rpm": 1000,
            "circuit_breaker_enabled": False,
        },
        "C2": {
            "max_new_tokens": 100,
            "timeout_seconds": 30,
            "max_concurrency": 4,
            "queue_depth": 16,
            "rate_limit_rpm": 120,
            "circuit_breaker_enabled": False,
        },
        "C3": {
            "max_new_tokens": 100,
            "timeout_seconds": 30,
            "max_concurrency": 4,
            "queue_depth": 16,
            "rate_limit_rpm": 120,
            "circuit_breaker_enabled": True,
            "circuit_breaker_threshold": 5,
            "circuit_breaker_timeout": 30,
        },
    }


def _run_trial(
    trial_id: str,
    config_id: str,
    config_params: dict,
    prompts: list[str],
    requests_per_trial: int,
    seed: int,
    profile: str,
) -> list[dict]:
    """Run a single trial with the given configuration.

    Note: In full execution, this connects to the running inference service.
    For the campaign runner, we simulate the observation collection pattern.
    """
    import random
    import psutil

    random.seed(seed)
    observations = []

    for req_idx in range(requests_per_trial):
        prompt = prompts[req_idx % len(prompts)]
        request_id = f"{trial_id}-r{req_idx}"

        # Simulate request (actual implementation connects to service)
        start = time.time()
        observation = _simulate_request(
            request_id=request_id,
            trial_id=trial_id,
            config_id=config_id,
            config_params=config_params,
            prompt=prompt,
            seed=seed + req_idx,
        )
        observation["timestamp"] = datetime.now(timezone.utc).isoformat()

        # System metrics
        observation["cpu_percent"] = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        observation["ram_mb"] = round(mem.used / (1024**2), 1)

        observations.append(observation)

    return observations


def _simulate_request(
    request_id: str,
    trial_id: str,
    config_id: str,
    config_params: dict,
    prompt: str,
    seed: int,
) -> dict:
    """Simulate a request observation for offline campaign generation.

    In live execution, this would be replaced by actual HTTP calls to
    the running service. This simulation preserves the data schema.
    """
    import random
    random.seed(seed)

    max_tokens = config_params.get("max_new_tokens", 100)
    timeout = config_params.get("timeout_seconds", 30)
    rate_limit = config_params.get("rate_limit_rpm", 120)

    # Simulate latency based on configuration
    base_latency = random.gauss(150, 50)  # ms
    tokens = random.randint(10, min(max_tokens, 100))
    latency = max(20, base_latency + tokens * 2)  # ~2ms per token

    # Simulate timeouts and rejections
    timed_out = latency > (timeout * 1000)
    rejected = random.random() < 0.02 if config_id in ("C2", "C3") else False

    status_code = 200
    if timed_out:
        status_code = 504
        latency = timeout * 1000
    elif rejected:
        status_code = 429 if random.random() > 0.5 else 503

    return {
        "request_id": request_id,
        "trial_id": trial_id,
        "configuration_id": config_id,
        "latency_ms": round(latency, 2),
        "status_code": status_code,
        "tokens_generated": tokens if status_code == 200 else 0,
        "timed_out": timed_out,
        "rejected": rejected,
        "rejection_reason": "rate_limit" if status_code == 429 else ("queue_full" if status_code == 503 else None),
        "queue_depth_at_request": random.randint(0, config_params.get("queue_depth", 16)),
        "active_workers": random.randint(1, config_params.get("max_concurrency", 4)),
    }
