"""Analysis, statistics, tables, and figures for publication."""

from pathlib import Path


def run_analysis(profile: str, input_dir: Path, output_dir: Path) -> int:
    """Run all analysis and generate publication artifacts."""
    from traceai.analysis.statistics import analyze_all_campaigns
    from traceai.analysis.tables import generate_all_tables
    from traceai.analysis.figures import generate_all_figures
    from traceai.analysis.narrative import generate_narrative

    output_dir.mkdir(parents=True, exist_ok=True)

    # Analyze campaigns
    stats = analyze_all_campaigns(input_dir, output_dir)

    # Generate LaTeX tables
    generate_all_tables(stats, output_dir)

    # Generate PDF figures
    generate_all_figures(stats, output_dir)

    # Generate narrative fragments
    generate_narrative(stats, output_dir, profile)

    return 0
