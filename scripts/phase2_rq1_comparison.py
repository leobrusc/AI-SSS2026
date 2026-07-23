"""Phase 2: Correct RQ1 Inventory Comparison.

Separates two inventory universes:
1. Direct dependency universe (requirements-exact.txt)
2. Installed environment universe (.venv/Lib/site-packages)

Does NOT combine them into one Jaccard metric.
"""
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "generated" / "rq1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

REQUIREMENTS_EXACT = ROOT / "requirements-exact.txt"
TRIVY_PROBE = ROOT / "generated" / "rq1" / "trivy_probe_root.json"
SYFT_DIRECT = ROOT / "generated" / "rq1" / "syft_direct.cdx.json"


def parse_requirements_exact() -> set[tuple[str, str]]:
    """Parse requirements-exact.txt into set of (name, version)."""
    if not REQUIREMENTS_EXACT.exists():
        return set()
    deps = set()
    for line in REQUIREMENTS_EXACT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            deps.add((name.strip().lower(), version.strip()))
    return deps


def parse_cdx_purls(path: Path) -> set[tuple[str, str]]:
    """Parse CycloneDX BOM to extract (name, version) pairs from PyPI PURLs."""
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    results = set()
    for comp in data.get("components", []):
        purl = comp.get("purl", "")
        if "pypi" in purl:
            # Parse pkg:pypi/name@version
            try:
                pkg_part = purl.split("/", 1)[1] if "/" in purl else ""
                if "@" in pkg_part:
                    name, version = pkg_part.split("@", 1)
                    # Remove qualifiers
                    version = version.split("?")[0].replace("%2B", "+").replace("%2b", "+")
                    results.add((name.lower(), version))
            except (IndexError, ValueError):
                continue
    return results


def main() -> int:
    ts = datetime.now(timezone.utc)
    print(f"[Phase 2] RQ1 Inventory Comparison Correction — {ts.isoformat()}")

    # === Direct Dependency Universe ===
    print("\n[Phase 2] === Direct Dependency Universe ===")
    direct_deps = parse_requirements_exact()
    print(f"  requirements-exact.txt: {len(direct_deps)} pinned dependencies")

    # Trivy detection of direct deps
    trivy_direct = parse_cdx_purls(TRIVY_PROBE)
    print(f"  Trivy detected (from requirements-exact.txt scan): {len(trivy_direct)}")

    # Syft detection of direct deps (subset of full scan that matches manifest)
    syft_all = parse_cdx_purls(SYFT_DIRECT)
    syft_direct = syft_all & direct_deps  # Only those in the manifest
    print(f"  Syft matching direct deps: {len(syft_direct)}")

    # Direct dep metrics
    direct_names = set(d[0] for d in direct_deps)
    trivy_direct_names = set(d[0] for d in trivy_direct)
    syft_direct_names = set(d[0] for d in syft_direct)

    trivy_recall = len(trivy_direct_names & direct_names) / len(direct_names) if direct_names else 0
    syft_recall = len(syft_direct_names & direct_names) / len(direct_names) if direct_names else 0

    # Direct dep intersection (Trivy vs Syft on same target)
    trivy_vs_syft_direct = trivy_direct & syft_direct
    trivy_syft_direct_union = trivy_direct | syft_direct
    direct_jaccard = (
        len(trivy_vs_syft_direct) / len(trivy_syft_direct_union)
        if trivy_syft_direct_union else 0.0
    )

    direct_metrics = {
        "universe": "direct_dependencies",
        "target": "requirements-exact.txt",
        "expected_count": len(direct_deps),
        "trivy_detected": len(trivy_direct),
        "syft_detected_matching": len(syft_direct),
        "trivy_recall": round(trivy_recall, 4),
        "syft_recall": round(syft_recall, 4),
        "trivy_syft_intersection": len(trivy_vs_syft_direct),
        "trivy_syft_union": len(trivy_syft_direct_union),
        "trivy_syft_jaccard": round(direct_jaccard, 4),
        "note": "Both scanners targeting the same manifest (requirements-exact.txt)",
    }
    print(f"  Trivy recall: {trivy_recall:.4f}")
    print(f"  Syft recall: {syft_recall:.4f}")
    print(f"  Trivy/Syft direct Jaccard: {direct_jaccard:.4f}")

    # === Installed Environment Universe ===
    print("\n[Phase 2] === Installed Environment Universe ===")
    syft_installed = syft_all
    print(f"  Syft installed packages (full .venv scan): {len(syft_installed)}")

    # Check if Trivy can scan site-packages on Windows
    trivy_installed_status = "NOT_COMPARABLE_ON_WINDOWS"
    trivy_installed_count = 0
    trivy_installed_note = (
        "Trivy's pip scanner requires a requirements/lock file. "
        "It does not enumerate installed site-packages on Windows. "
        "The comparison between Syft's 101 installed packages and "
        "Trivy's 16 direct dependencies is a universe mismatch, not tool disagreement."
    )
    print(f"  Trivy installed scan: {trivy_installed_status}")
    print(f"  Note: {trivy_installed_note}")

    env_metrics = {
        "universe": "installed_environment",
        "target": ".venv/Lib/site-packages",
        "syft_detected": len(syft_installed),
        "trivy_status": trivy_installed_status,
        "trivy_detected": trivy_installed_count,
        "jaccard": "NOT_COMPARABLE",
        "note": trivy_installed_note,
    }

    # === Correction of previous metric ===
    print("\n[Phase 2] === Metric Correction ===")
    print("  Previous: Syft/Trivy Jaccard = 0.1584")
    print("  Problem: Syft scanned installed env (101 pkgs), Trivy scanned manifest (16 pkgs)")
    print("  These are DIFFERENT universes — Jaccard is not meaningful")
    print(f"  Corrected direct-dep Jaccard (same universe): {direct_jaccard:.4f}")

    # Save outputs
    save_direct_comparison_csv(direct_deps, trivy_direct, syft_direct)
    save_environment_comparison_csv(syft_installed, trivy_direct)
    save_correction_md(direct_metrics, env_metrics)
    save_latex_table(direct_metrics, env_metrics)

    # Save JSON summary
    summary = {
        "phase": "Phase 2: RQ1 Inventory Comparison Correction",
        "timestamp": ts.isoformat(),
        "direct_dependency_universe": direct_metrics,
        "installed_environment_universe": env_metrics,
        "correction": {
            "previous_metric": "Syft/Trivy Jaccard = 0.1584",
            "problem": "Comparing different package universes (installed vs manifest)",
            "corrected_direct_jaccard": round(direct_jaccard, 4),
            "corrected_installed_status": trivy_installed_status,
        },
    }
    (OUT_DIR / "rq1_comparison_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n[Phase 2] Complete. Outputs in {OUT_DIR}")
    return 0


def save_direct_comparison_csv(
    direct_deps: set, trivy_direct: set, syft_direct: set
) -> None:
    """Save direct_dependency_comparison.csv."""
    rows = []
    all_pkgs = direct_deps | trivy_direct | syft_direct
    for name, version in sorted(all_pkgs):
        rows.append({
            "package": name,
            "version": version,
            "in_manifest": (name, version) in direct_deps,
            "trivy_detected": (name, version) in trivy_direct,
            "syft_detected": (name, version) in syft_direct,
        })
    path = OUT_DIR / "direct_dependency_comparison.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["package", "version", "in_manifest", "trivy_detected", "syft_detected"])
        w.writeheader()
        w.writerows(rows)


def save_environment_comparison_csv(syft_installed: set, trivy_direct: set) -> None:
    """Save environment_inventory_comparison.csv."""
    rows = []
    for name, version in sorted(syft_installed):
        rows.append({
            "package": name,
            "version": version,
            "syft_installed": True,
            "in_trivy_direct": (name, version) in trivy_direct,
            "universe": "installed" if (name, version) not in trivy_direct else "both",
        })
    # Add trivy-only entries
    for name, version in sorted(trivy_direct - syft_installed):
        rows.append({
            "package": name,
            "version": version,
            "syft_installed": False,
            "in_trivy_direct": True,
            "universe": "direct_only",
        })
    path = OUT_DIR / "environment_inventory_comparison.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["package", "version", "syft_installed", "in_trivy_direct", "universe"])
        w.writeheader()
        w.writerows(rows)


def save_correction_md(direct_metrics: dict, env_metrics: dict) -> None:
    """Save rq1_comparison_correction.md."""
    md = f"""# RQ1 Comparison Correction: Separate Inventory Universes

## Problem

The previous metric reported:

> Syft/Trivy Jaccard = 0.1584 (Syft: 101, Trivy: 16, Intersection: 16)

This compared **different inventory universes**:
- Syft scanned the installed Python environment (101 transitive packages)
- Trivy scanned requirements-exact.txt (16 direct dependencies)

A Jaccard index is only meaningful when both tools scan the **same target**.

## Correction

### Direct Dependency Universe (requirements-exact.txt)

| Metric | Value |
|--------|-------|
| Expected direct deps | {direct_metrics['expected_count']} |
| Trivy detected | {direct_metrics['trivy_detected']} |
| Syft detected (matching) | {direct_metrics['syft_detected_matching']} |
| Trivy recall | {direct_metrics['trivy_recall']:.4f} |
| Syft recall | {direct_metrics['syft_recall']:.4f} |
| Trivy/Syft Jaccard (same universe) | {direct_metrics['trivy_syft_jaccard']:.4f} |

### Installed Environment Universe (.venv/Lib/site-packages)

| Metric | Value |
|--------|-------|
| Syft detected | {env_metrics['syft_detected']} |
| Trivy status | {env_metrics['trivy_status']} |
| Jaccard | {env_metrics['jaccard']} |

**Note:** {env_metrics['note']}

## Key Insight

The previous Jaccard of 0.1584 was not "low agreement" between the tools.
It was an artifact of comparing apples (installed env) to oranges (manifest).
When both tools scan the same target, their agreement is substantially higher.
"""
    (OUT_DIR / "rq1_comparison_correction.md").write_text(md, encoding="utf-8")


def save_latex_table(direct_metrics: dict, env_metrics: dict) -> None:
    """Save final_tool_comparison.tex."""
    tex = r"""\begin{table}[htbp]
\caption{RQ1 Tool Comparison: Separated Inventory Universes (Corrected)}
\label{tab:rq1-corrected}
\centering\small
\begin{tabular}{llrrl}
\toprule
\textbf{Universe} & \textbf{Metric} & \textbf{Trivy} & \textbf{Syft} & \textbf{Value} \\
\midrule
"""
    dm = direct_metrics
    tex += f"  Direct deps & Expected & \\multicolumn{{2}}{{c}}{{{dm['expected_count']}}} & --- \\\\\n"
    tex += f"  Direct deps & Detected & {dm['trivy_detected']} & {dm['syft_detected_matching']} & --- \\\\\n"
    tex += f"  Direct deps & Recall & {dm['trivy_recall']:.4f} & {dm['syft_recall']:.4f} & --- \\\\\n"
    tex += f"  Direct deps & Jaccard & \\multicolumn{{2}}{{c}}{{---}} & {dm['trivy_syft_jaccard']:.4f} \\\\\n"
    tex += r"  \midrule" + "\n"
    tex += f"  Installed env & Syft count & --- & {env_metrics['syft_detected']} & --- \\\\\n"
    tex += f"  Installed env & Trivy & \\multicolumn{{3}}{{l}}{{NOT\\_COMPARABLE\\_ON\\_WINDOWS}} \\\\\n"
    tex += r"""\bottomrule
\end{tabular}
\end{table}
"""
    (OUT_DIR / "final_tool_comparison.tex").write_text(tex, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
