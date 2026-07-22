"""Narrative generation for paper fragments.

IMPORTANT: The narrative generator refuses to claim improvement when
comparison data or confidence intervals are absent.
"""

from pathlib import Path
from typing import Any

from traceai.logging_config import get_logger

logger = get_logger("analysis.narrative")


def generate_narrative(stats: dict[str, Any], output_dir: Path, profile: str) -> None:
    """Generate paper narrative fragments from analysis results."""
    output_dir.mkdir(parents=True, exist_ok=True)

    fragments_dir = output_dir / ".." / "paper" / "fragments"
    fragments_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "% Auto-generated narrative fragment",
        f"% Profile: {profile}",
        "% WARNING: These are preliminary quick-campaign results.",
        "% Do not present as full campaign evidence.",
        "",
    ]

    # Security narrative
    security = stats.get("security", {})
    if security.get("available"):
        lines.extend(_security_narrative(security, profile))
    else:
        lines.append("% Security campaign: NOT EXECUTED")
        lines.append("")

    # Availability narrative
    availability = stats.get("availability", {})
    if availability.get("available"):
        lines.extend(_availability_narrative(availability, profile))
    else:
        lines.append("% Availability campaign: NOT EXECUTED")
        lines.append("")

    path = output_dir / "narrative_fragment.tex"
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Narrative fragment saved: {path}")


def _security_narrative(security: dict, profile: str) -> list[str]:
    """Generate security results narrative."""
    lines = []
    summary = security.get("summary", {})
    scenarios = security.get("scenarios", {})

    lines.append(r"\paragraph{Provenance and Integrity (RQ2)}")
    lines.append(
        f"The security campaign executed {summary.get('total_observations', 'N/A')} "
        f"observations across {summary.get('scenarios_tested', 'N/A')} scenarios "
        f"using the \\texttt{{{profile}}} profile."
    )

    # Report detection rates with CIs
    for sid in sorted(scenarios.keys()):
        data = scenarios[sid]
        ci = data.get("wilson_ci_95", [0, 0])
        rate = data.get("detection_rate", 0)

        if rate == 1.0 and ci[0] >= 0.8:
            lines.append(
                f"Scenario {sid}: detection rate {rate:.3f} "
                f"(95\\% Wilson CI: [{ci[0]:.3f}, {ci[1]:.3f}])."
            )
        elif rate < 1.0:
            lines.append(
                f"Scenario {sid}: detection rate {rate:.3f} "
                f"(95\\% Wilson CI: [{ci[0]:.3f}, {ci[1]:.3f}]). "
                f"\\textbf{{Requires investigation.}}"
            )

    fp = summary.get("total_false_positives", 0)
    fn = summary.get("total_false_negatives", 0)
    if fp == 0 and fn == 0:
        lines.append("No false positives or false negatives observed in this campaign.")
    else:
        lines.append(f"False positives: {fp}. False negatives: {fn}.")

    # Refuse to claim if insufficient data
    if summary.get("total_observations", 0) < 100:
        lines.append("")
        lines.append(
            "\\textit{Note: These results are from a quick campaign "
            "with limited trial count. Full campaign required for "
            "publication-quality claims.}"
        )

    lines.append("")
    return lines


def _availability_narrative(availability: dict, profile: str) -> list[str]:
    """Generate availability results narrative."""
    lines = []
    summary = availability.get("summary", {})
    configs = availability.get("configurations", {})

    lines.append(r"\paragraph{Runtime Controls and Availability (RQ4)}")
    lines.append(
        f"The availability campaign collected {summary.get('total_observations', 'N/A')} "
        f"request observations across {summary.get('configurations_tested', 'N/A')} "
        f"configurations using the \\texttt{{{profile}}} profile."
    )

    for cid in sorted(configs.keys()):
        data = configs[cid]
        latency = data.get("latency", {})
        lines.append(
            f"Configuration {cid}: success rate {data.get('success_rate', 0):.3f}, "
            f"P50={latency.get('p50', 0):.1f}ms, "
            f"P95={latency.get('p95', 0):.1f}ms, "
            f"P99={latency.get('p99', 0):.1f}ms."
        )

    # Check for comparison data
    comparison = availability.get("c0_vs_c3_comparison")
    if comparison and comparison.get("p_value") is not None:
        lines.append(
            f"C0 vs C3 comparison: median difference "
            f"{comparison.get('median_difference', 'N/A'):.1f}ms "
            f"(95\\% CI: [{comparison.get('ci_lower', 'N/A'):.1f}, "
            f"{comparison.get('ci_upper', 'N/A'):.1f}]), "
            f"Wilcoxon p={comparison.get('p_value', 'N/A'):.4f}, "
            f"r={comparison.get('effect_size_r', 'N/A'):.3f}."
        )
    else:
        lines.append(
            "\\textit{Paired comparison not available: insufficient "
            "trial-level data for Wilcoxon signed-rank test.}"
        )

    # Refuse to claim improvement without evidence
    if summary.get("total_observations", 0) < 100:
        lines.append("")
        lines.append(
            "\\textit{Note: Quick campaign results are preliminary. "
            "Cannot claim statistically significant improvement without "
            "full 30-trial campaign with proper confidence intervals.}"
        )

    lines.append("")
    return lines
