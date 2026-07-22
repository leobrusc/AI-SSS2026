"""Publication-quality figure generation using Matplotlib (no Seaborn)."""

import json
from pathlib import Path
from typing import Any

import numpy as np

from traceai.logging_config import get_logger

logger = get_logger("analysis.figures")


def generate_all_figures(stats: dict[str, Any], output_dir: Path) -> None:
    """Generate all publication figures as vector PDFs."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if stats.get("availability", {}).get("available"):
        _generate_latency_cdf(stats["availability"], output_dir)
        _generate_resource_summary(stats["availability"], output_dir)

    # GPU memory timeseries placeholder
    _generate_gpu_memory_placeholder(output_dir)


def _generate_latency_cdf(avail_stats: dict, output_dir: Path) -> None:
    """Generate latency CDF figure comparing configurations."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 1, figsize=(6, 4))

    configurations = avail_stats.get("configurations", {})
    colors = {"C0": "#1f77b4", "C1": "#ff7f0e", "C2": "#2ca02c", "C3": "#d62728"}
    linestyles = {"C0": "-", "C1": "--", "C2": "-.", "C3": ":"}

    for config_id in sorted(configurations.keys()):
        data = configurations[config_id]
        latency = data.get("latency", {})

        # Reconstruct approximate CDF from percentiles
        # For full results this would use raw data
        p50 = latency.get("p50", 100)
        p95 = latency.get("p95", 200)
        p99 = latency.get("p99", 300)

        # Generate synthetic CDF points from percentiles
        x_points = np.linspace(0, p99 * 1.2, 100)
        # Log-normal approximation
        mu = np.log(p50)
        sigma = (np.log(p95) - np.log(p50)) / 1.645 if p95 > p50 else 0.5
        from scipy.stats import lognorm
        cdf_values = lognorm.cdf(x_points, sigma, scale=np.exp(mu))

        ax.plot(
            x_points, cdf_values,
            label=config_id,
            color=colors.get(config_id, "gray"),
            linestyle=linestyles.get(config_id, "-"),
            linewidth=1.5,
        )

    ax.set_xlabel("Latency (ms)")
    ax.set_ylabel("CDF")
    ax.set_title("Request Latency CDF by Configuration")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)
    ax.set_xlim(left=0)
    ax.set_ylim(0, 1)

    fig.tight_layout()
    path = output_dir / "latency_cdf.pdf"
    fig.savefig(path, format="pdf", dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Latency CDF figure saved: {path}")


def _generate_resource_summary(avail_stats: dict, output_dir: Path) -> None:
    """Generate resource utilization summary figure."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    configurations = avail_stats.get("configurations", {})
    config_ids = sorted(configurations.keys())

    if not config_ids:
        return

    fig, axes = plt.subplots(1, 3, figsize=(10, 3.5))

    # Success rates
    success_rates = [configurations[c].get("success_rate", 0) for c in config_ids]
    axes[0].bar(config_ids, success_rates, color=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"])
    axes[0].set_ylabel("Success Rate")
    axes[0].set_title("Success Rate")
    axes[0].set_ylim(0, 1.05)
    axes[0].grid(True, alpha=0.3, axis="y")

    # P50 latency
    p50s = [configurations[c].get("latency", {}).get("p50", 0) for c in config_ids]
    axes[1].bar(config_ids, p50s, color=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"])
    axes[1].set_ylabel("Latency (ms)")
    axes[1].set_title("Median Latency (P50)")
    axes[1].grid(True, alpha=0.3, axis="y")

    # Throughput
    throughputs = [configurations[c].get("throughput_rps", 0) for c in config_ids]
    axes[2].bar(config_ids, throughputs, color=["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"])
    axes[2].set_ylabel("Requests/s")
    axes[2].set_title("Throughput")
    axes[2].grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    path = output_dir / "resource_summary.pdf"
    fig.savefig(path, format="pdf", dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Resource summary figure saved: {path}")


def _generate_gpu_memory_placeholder(output_dir: Path) -> None:
    """Generate GPU memory timeseries placeholder."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 1, figsize=(6, 3))
    ax.text(
        0.5, 0.5,
        "GPU Memory Timeseries\n(Requires GPU telemetry data)",
        ha="center", va="center", fontsize=12, color="gray",
        transform=ax.transAxes,
    )
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("GPU Memory (MB)")
    ax.set_title("GPU Memory Usage During Campaign")

    fig.tight_layout()
    path = output_dir / "gpu_memory_timeseries.pdf"
    fig.savefig(path, format="pdf", dpi=300, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"GPU memory placeholder saved: {path}")
