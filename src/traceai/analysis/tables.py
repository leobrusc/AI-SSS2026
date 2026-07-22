"""LaTeX table generation for publication."""

from pathlib import Path
from typing import Any

from traceai.environment import escape_latex
from traceai.logging_config import get_logger

logger = get_logger("analysis.tables")


def generate_all_tables(stats: dict[str, Any], output_dir: Path) -> None:
    """Generate all LaTeX tables from analysis results."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if stats.get("security", {}).get("available"):
        _generate_security_table(stats["security"], output_dir)

    if stats.get("availability", {}).get("available"):
        _generate_availability_table(stats["availability"], output_dir)

    _generate_summary_table(stats, output_dir)


def _generate_security_table(security_stats: dict, output_dir: Path) -> None:
    """Generate results_security_table.tex."""
    scenarios = security_stats.get("scenarios", {})

    lines = [
        r"\begin{table}[htbp]",
        r"\caption{Security Campaign Results (Quick Campaign -- Preliminary)}",
        r"\label{tab:security-results}",
        r"\centering",
        r"\small",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"\textbf{Scenario} & \textbf{Trials} & \textbf{Rate} & \textbf{95\% CI} & \textbf{Latency (ms)} \\",
        r"\midrule",
    ]

    for scenario_id in sorted(scenarios.keys()):
        data = scenarios[scenario_id]
        ci = data.get("wilson_ci_95", [0, 0])
        ci_str = f"[{ci[0]:.3f}, {ci[1]:.3f}]"
        latency = data.get("latency", {}).get("p50", 0)

        lines.append(
            f"  {escape_latex(scenario_id)} & "
            f"{data['trials']} & "
            f"{data['detection_rate']:.3f} & "
            f"{ci_str} & "
            f"{latency:.1f} \\\\"
        )

    summary = security_stats.get("summary", {})
    lines.extend([
        r"\midrule",
        f"  Total & {summary.get('total_observations', 'N/A')} & -- & -- & -- \\\\",
        f"  FP/FN & -- & {summary.get('total_false_positives', 0)}/{summary.get('total_false_negatives', 0)} & -- & -- \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])

    path = output_dir / "results_security_table.tex"
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Security table saved: {path}")


def _generate_availability_table(avail_stats: dict, output_dir: Path) -> None:
    """Generate results_availability_table.tex."""
    configurations = avail_stats.get("configurations", {})

    lines = [
        r"\begin{table}[htbp]",
        r"\caption{Availability Campaign Results (Quick Campaign -- Preliminary)}",
        r"\label{tab:availability-results}",
        r"\centering",
        r"\small",
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"\textbf{Config} & \textbf{N} & \textbf{Success} & \textbf{P50 (ms)} & \textbf{P95 (ms)} & \textbf{P99 (ms)} \\",
        r"\midrule",
    ]

    for config_id in sorted(configurations.keys()):
        data = configurations[config_id]
        latency = data.get("latency", {})

        lines.append(
            f"  {escape_latex(config_id)} & "
            f"{data['observations']} & "
            f"{data['success_rate']:.3f} & "
            f"{latency.get('p50', 0):.1f} & "
            f"{latency.get('p95', 0):.1f} & "
            f"{latency.get('p99', 0):.1f} \\\\"
        )

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])

    path = output_dir / "results_availability_table.tex"
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Availability table saved: {path}")


def _generate_summary_table(stats: dict, output_dir: Path) -> None:
    """Generate results_summary.tex answering RQ1-RQ4."""
    lines = [
        r"% TraceAI Results Summary -- Generated from measured quick-campaign data",
        r"% Profile: local | Quick campaign (preliminary)",
        r"",
        r"\subsection{Summary of Results}",
        r"",
    ]

    # RQ1
    lines.append(r"\paragraph{RQ1 (BOM Coverage)}")
    lines.append(r"Ground-truth dependency graph constructed. ")
    lines.append(r"Coverage metrics require external scanner comparison (Syft/Trivy).")
    lines.append(r"When scanners are unavailable, comparison is marked N/A.")
    lines.append(r"")

    # RQ2
    security = stats.get("security", {})
    if security.get("available"):
        summary = security.get("summary", {})
        lines.append(r"\paragraph{RQ2 (Provenance Gates)}")
        lines.append(
            f"Security campaign: {summary.get('total_observations', 'N/A')} observations "
            f"across {summary.get('scenarios_tested', 'N/A')} scenarios. "
            f"False positives: {summary.get('total_false_positives', 'N/A')}, "
            f"False negatives: {summary.get('total_false_negatives', 'N/A')}."
        )
        lines.append(r"")
    else:
        lines.append(r"\paragraph{RQ2 (Provenance Gates)} N/A -- campaign not executed.")
        lines.append(r"")

    # RQ3
    lines.append(r"\paragraph{RQ3 (VEX Effectiveness)}")
    lines.append(r"VEX evaluation requires external scanners (Trivy/Grype). ")
    lines.append(r"When unavailable, scanner agreement is marked N/A.")
    lines.append(r"")

    # RQ4
    availability = stats.get("availability", {})
    if availability.get("available"):
        summary = availability.get("summary", {})
        lines.append(r"\paragraph{RQ4 (Runtime Controls)}")
        lines.append(
            f"Availability campaign: {summary.get('total_observations', 'N/A')} observations "
            f"across {summary.get('configurations_tested', 'N/A')} configurations."
        )
    else:
        lines.append(r"\paragraph{RQ4 (Runtime Controls)} N/A -- campaign not executed.")

    path = output_dir / "results_summary.tex"
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Summary table saved: {path}")
