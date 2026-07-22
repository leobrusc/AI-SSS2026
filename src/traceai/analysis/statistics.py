"""Statistical analysis for campaign results."""

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats as scipy_stats

from traceai.logging_config import get_logger

logger = get_logger("analysis.statistics")


def wilson_confidence_interval(
    successes: int, trials: int, confidence: float = 0.95
) -> tuple[float, float]:
    """Compute Wilson score confidence interval for binary proportion.

    More appropriate than normal approximation for small samples or
    extreme proportions.
    """
    if trials == 0:
        return (0.0, 0.0)

    z = scipy_stats.norm.ppf(1 - (1 - confidence) / 2)
    p_hat = successes / trials
    denominator = 1 + z**2 / trials

    center = (p_hat + z**2 / (2 * trials)) / denominator
    margin = (z / denominator) * math.sqrt(
        p_hat * (1 - p_hat) / trials + z**2 / (4 * trials**2)
    )

    return (max(0.0, center - margin), min(1.0, center + margin))


def block_bootstrap_ci(
    data: np.ndarray,
    statistic_fn=np.median,
    n_bootstrap: int = 10000,
    confidence: float = 0.95,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Compute bootstrap confidence interval for a statistic.

    Returns (estimate, lower, upper).
    """
    rng = np.random.default_rng(seed)
    n = len(data)
    if n == 0:
        return (0.0, 0.0, 0.0)

    estimate = float(statistic_fn(data))
    bootstrap_stats = np.empty(n_bootstrap)

    for i in range(n_bootstrap):
        sample = rng.choice(data, size=n, replace=True)
        bootstrap_stats[i] = statistic_fn(sample)

    alpha = 1 - confidence
    lower = float(np.percentile(bootstrap_stats, 100 * alpha / 2))
    upper = float(np.percentile(bootstrap_stats, 100 * (1 - alpha / 2)))

    return (estimate, lower, upper)


def compute_percentiles(data: np.ndarray) -> dict[str, float]:
    """Compute P50, P95, P99 from data."""
    if len(data) == 0:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    return {
        "p50": float(np.percentile(data, 50)),
        "p95": float(np.percentile(data, 95)),
        "p99": float(np.percentile(data, 99)),
    }


def wilcoxon_signed_rank(
    baseline: np.ndarray, protected: np.ndarray
) -> dict[str, Any]:
    """Wilcoxon signed-rank test for paired samples.

    Reports statistic, p-value, effect size (r = Z/sqrt(N)), and
    median difference with bootstrap CI.
    """
    if len(baseline) != len(protected) or len(baseline) < 3:
        return {
            "statistic": None,
            "p_value": None,
            "effect_size_r": None,
            "median_difference": None,
            "ci_lower": None,
            "ci_upper": None,
            "note": "Insufficient paired observations",
        }

    differences = protected - baseline
    non_zero = differences[differences != 0]

    if len(non_zero) < 3:
        return {
            "statistic": None,
            "p_value": None,
            "effect_size_r": None,
            "median_difference": float(np.median(differences)),
            "ci_lower": None,
            "ci_upper": None,
            "note": "Insufficient non-zero differences",
        }

    try:
        stat, p_value = scipy_stats.wilcoxon(non_zero)
        # Effect size r = Z / sqrt(N)
        n = len(non_zero)
        z = scipy_stats.norm.ppf(1 - p_value / 2)
        effect_size = z / math.sqrt(n)

        median_diff, ci_lower, ci_upper = block_bootstrap_ci(differences)

        return {
            "statistic": float(stat),
            "p_value": float(p_value),
            "effect_size_r": round(float(effect_size), 4),
            "median_difference": median_diff,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "n_pairs": n,
        }
    except Exception as e:
        return {
            "statistic": None,
            "p_value": None,
            "effect_size_r": None,
            "median_difference": float(np.median(differences)),
            "error": str(e),
        }


def analyze_security_campaign(results_path: Path) -> dict[str, Any]:
    """Analyze security campaign results."""
    if not results_path.exists():
        return {"available": False, "error": "Results file not found"}

    with open(results_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    if not results:
        return {"available": False, "error": "No results"}

    # Group by scenario
    by_scenario: dict[str, list] = {}
    for r in results:
        sid = r["scenario_id"]
        by_scenario.setdefault(sid, []).append(r)

    analysis = {"available": True, "scenarios": {}}

    for scenario_id, trials in by_scenario.items():
        n_trials = len(trials)
        detections = sum(
            1 for t in trials
            if (scenario_id != "S0" and t["decision"] != "APPROVED")
            or (scenario_id == "S0" and t["decision"] == "APPROVED")
        )
        fp = sum(1 for t in trials if t.get("false_positive", False))
        fn = sum(1 for t in trials if t.get("false_negative", False))

        detection_rate = detections / n_trials if n_trials > 0 else 0
        ci_low, ci_high = wilson_confidence_interval(detections, n_trials)

        latencies = [t["detection_latency_ms"] for t in trials]
        lat_array = np.array(latencies)

        analysis["scenarios"][scenario_id] = {
            "trials": n_trials,
            "correct_decisions": detections,
            "detection_rate": round(detection_rate, 4),
            "wilson_ci_95": [round(ci_low, 4), round(ci_high, 4)],
            "false_positives": fp,
            "false_negatives": fn,
            "latency": compute_percentiles(lat_array),
            "latency_mean_ms": round(float(np.mean(lat_array)), 3),
        }

    # Overall
    total_fp = sum(1 for r in results if r.get("false_positive", False))
    total_fn = sum(1 for r in results if r.get("false_negative", False))
    analysis["summary"] = {
        "total_observations": len(results),
        "total_false_positives": total_fp,
        "total_false_negatives": total_fn,
        "scenarios_tested": len(by_scenario),
    }

    return analysis


def analyze_availability_campaign(results_path: Path) -> dict[str, Any]:
    """Analyze availability campaign results."""
    if not results_path.exists():
        return {"available": False, "error": "Results file not found"}

    with open(results_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    if not results:
        return {"available": False, "error": "No results"}

    # Group by configuration
    by_config: dict[str, list] = {}
    for r in results:
        cid = r["configuration_id"]
        by_config.setdefault(cid, []).append(r)

    analysis = {"available": True, "configurations": {}}

    for config_id, observations in by_config.items():
        latencies = np.array([o["latency_ms"] for o in observations])
        success_count = sum(1 for o in observations if o["status_code"] == 200)
        timeout_count = sum(1 for o in observations if o.get("timed_out", False))
        rejected_count = sum(1 for o in observations if o.get("rejected", False))

        success_rate = success_count / len(observations) if observations else 0

        # Throughput (requests/second approximation)
        total_time_s = sum(o["latency_ms"] for o in observations) / 1000
        throughput = len(observations) / total_time_s if total_time_s > 0 else 0

        percentiles = compute_percentiles(latencies)
        median_est, ci_low, ci_high = block_bootstrap_ci(latencies)

        analysis["configurations"][config_id] = {
            "observations": len(observations),
            "success_rate": round(success_rate, 4),
            "timeout_count": timeout_count,
            "rejected_count": rejected_count,
            "latency": percentiles,
            "latency_bootstrap_ci_95": [round(ci_low, 2), round(ci_high, 2)],
            "throughput_rps": round(throughput, 2),
            "tokens_generated_mean": round(
                float(np.mean([o["tokens_generated"] for o in observations])), 1
            ),
        }

    # Paired comparison: C0 vs C3
    if "C0" in by_config and "C3" in by_config:
        c0_medians = _trial_medians(by_config["C0"])
        c3_medians = _trial_medians(by_config["C3"])
        min_len = min(len(c0_medians), len(c3_medians))
        if min_len >= 3:
            comparison = wilcoxon_signed_rank(
                np.array(c0_medians[:min_len]),
                np.array(c3_medians[:min_len]),
            )
            analysis["c0_vs_c3_comparison"] = comparison

    analysis["summary"] = {
        "total_observations": len(results),
        "configurations_tested": len(by_config),
    }

    return analysis


def _trial_medians(observations: list[dict]) -> list[float]:
    """Compute median latency per trial."""
    by_trial: dict[str, list[float]] = {}
    for o in observations:
        tid = o["trial_id"]
        by_trial.setdefault(tid, []).append(o["latency_ms"])
    return [float(np.median(v)) for v in by_trial.values()]


def analyze_all_campaigns(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Analyze all available campaign results."""
    results = {}

    # Find latest security campaign
    raw_dir = input_dir / "raw"
    if raw_dir.exists():
        security_dirs = sorted(raw_dir.glob("security-*"))
        if security_dirs:
            latest = security_dirs[-1]
            results_file = latest / "security_results.json"
            results["security"] = analyze_security_campaign(results_file)

        availability_dirs = sorted(raw_dir.glob("availability-*"))
        if availability_dirs:
            latest = availability_dirs[-1]
            results_file = latest / "availability_results.json"
            results["availability"] = analyze_availability_campaign(results_file)

        overhead_dirs = sorted(raw_dir.glob("overhead-*"))
        if overhead_dirs:
            latest = overhead_dirs[-1]
            results_file = latest / "overhead_results.json"
            if results_file.exists():
                with open(results_file, "r", encoding="utf-8") as f:
                    results["overhead"] = {"available": True, "measurements": json.load(f)}

    # Save combined analysis
    analysis_path = output_dir / "analysis_results.json"
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info(f"Analysis results saved: {analysis_path}")
    return results
