"""Phase 4: Clean-Clone Reproducibility Test.

Clones the repository to a temporary directory, installs dependencies,
runs key scripts, and compares regenerated artifacts with originals.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
REPRO_DIR = Path(r"C:\Users\leolima\Documents\traceai-repro-check")
OUT_DIR = ROOT / "generated" / "reproducibility"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT = 120  # seconds per subprocess


def run_cmd(cmd: list[str], cwd: Path, timeout: int = TIMEOUT,
            env: dict = None) -> tuple[int, str, str, float]:
    """Run a command with timeout, returning (exitcode, stdout, stderr, elapsed)."""
    print(f"  CMD: {' '.join(cmd)}")
    ts = time.perf_counter()
    try:
        result = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, env=env,
        )
        elapsed = time.perf_counter() - ts
        print(f"  Exit: {result.returncode}, Elapsed: {elapsed:.1f}s")
        return result.returncode, result.stdout, result.stderr, elapsed
    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - ts
        print(f"  TIMEOUT after {elapsed:.1f}s")
        return -1, "", "TIMEOUT", elapsed


def main() -> int:
    ts_start = datetime.now(timezone.utc)
    print(f"[Phase 4] Clean-Clone Reproducibility Test — {ts_start.isoformat()}")
    print(f"[Phase 4] Clone target: {REPRO_DIR}")

    results = {
        "timestamp": ts_start.isoformat(),
        "clone_dir": str(REPRO_DIR),
        "source_dir": str(ROOT),
        "steps": [],
        "comparisons": [],
        "passed": False,
    }

    # Clean up any previous clone
    if REPRO_DIR.exists():
        print("[Phase 4] Removing previous clone...")
        shutil.rmtree(REPRO_DIR, ignore_errors=True)

    try:
        # Step 1: Clone
        print("\n[Phase 4] Step 1: Clone repository")
        rc, out, err, elapsed = run_cmd(
            ["git", "clone", str(ROOT), str(REPRO_DIR)],
            cwd=ROOT.parent
        )
        results["steps"].append({"step": "git_clone", "exit_code": rc, "elapsed": elapsed})
        if rc != 0:
            print(f"  FAILED: {err[:300]}")
            results["failure_reason"] = "Clone failed"
            save_results(results)
            return 1

        # Step 2: Checkout and confirm clean
        print("\n[Phase 4] Step 2: Confirm clean status")
        rc, out, err, elapsed = run_cmd(["git", "status", "--short"], cwd=REPRO_DIR)
        results["steps"].append({"step": "git_status", "exit_code": rc, "output": out.strip()})
        if out.strip():
            print(f"  WARNING: Not clean: {out.strip()}")

        # Step 3: Create venv and install
        print("\n[Phase 4] Step 3: Create virtual environment")
        venv_path = REPRO_DIR / ".venv"
        rc, out, err, elapsed = run_cmd(
            [sys.executable, "-m", "venv", str(venv_path)], cwd=REPRO_DIR
        )
        results["steps"].append({"step": "create_venv", "exit_code": rc, "elapsed": elapsed})
        if rc != 0:
            results["failure_reason"] = "Venv creation failed"
            save_results(results)
            return 1

        # Determine pip and python in the clone venv
        clone_python = str(venv_path / "Scripts" / "python.exe")
        clone_pip = str(venv_path / "Scripts" / "pip.exe")

        # Step 4: Install dependencies
        print("\n[Phase 4] Step 4: Install dependencies")
        # Install the package with all dependencies from pyproject.toml
        rc, out, err, elapsed = run_cmd(
            [clone_pip, "install", "-e", ".[dev]", "--quiet"],
            cwd=REPRO_DIR, timeout=600
        )
        results["steps"].append({"step": "pip_install", "exit_code": rc, "elapsed": elapsed})
        if rc != 0:
            print(f"  Install errors (last 300): {err[-300:]}")
            # Try without [dev] extras
            print("  Retrying without dev extras...")
            rc, out, err, elapsed = run_cmd(
                [clone_pip, "install", "-e", ".", "--quiet"],
                cwd=REPRO_DIR, timeout=600
            )
            results["steps"].append({"step": "pip_install_retry", "exit_code": rc, "elapsed": elapsed})

        # Step 5: Run Phase 1 (RQ3) - requires results/rq3 from campaign
        print("\n[Phase 4] Step 5: Run Phase 1 (canonical RQ3)")
        # Phase 1 depends on results/rq3/ which is produced by security campaign
        # Copy the scanner results from original (simulates running the campaign)
        scanner_src = ROOT / "results" / "rq3"
        scanner_dst = REPRO_DIR / "results" / "rq3"
        if scanner_src.exists():
            shutil.copytree(str(scanner_src), str(scanner_dst), dirs_exist_ok=True)
            print("  Copied scanner results from original (campaign output)")
        rc, out, err, elapsed = run_cmd(
            [clone_python, "-X", "utf8", "scripts/phase1_canonical_rq3.py"],
            cwd=REPRO_DIR
        )
        results["steps"].append({"step": "phase1_rq3", "exit_code": rc, "elapsed": elapsed})
        if rc != 0:
            print(f"  Phase 1 output: {out[-500:]}")
            print(f"  Phase 1 errors: {err[-500:]}")

        # Step 6: Run Phase 2 (RQ1)
        print("\n[Phase 4] Step 6: Run Phase 2 (RQ1 comparison)")
        # Phase 2 depends on generated/rq1/ (Trivy probe and Syft outputs)
        gen_rq1_src = ROOT / "generated" / "rq1"
        gen_rq1_dst = REPRO_DIR / "generated" / "rq1"
        if gen_rq1_src.exists():
            gen_rq1_dst.mkdir(parents=True, exist_ok=True)
            for f in gen_rq1_src.iterdir():
                if f.is_file() and f.suffix == ".json":
                    shutil.copy2(str(f), str(gen_rq1_dst / f.name))
            print("  Copied generated/rq1 scanner outputs from original")
        rc, out, err, elapsed = run_cmd(
            [clone_python, "-X", "utf8", "scripts/phase2_rq1_comparison.py"],
            cwd=REPRO_DIR
        )
        results["steps"].append({"step": "phase2_rq1", "exit_code": rc, "elapsed": elapsed})
        if rc != 0:
            print(f"  Phase 2 errors: {err[-500:]}")

        # Step 7: Run unit tests
        print("\n[Phase 4] Step 7: Run unit tests")
        rc, out, err, elapsed = run_cmd(
            [clone_python, "-m", "pytest", "tests/unit", "-q", "--tb=line"],
            cwd=REPRO_DIR, timeout=120
        )
        results["steps"].append({"step": "pytest", "exit_code": rc, "elapsed": elapsed,
                                  "output_tail": out[-500:]})
        print(f"  Test output: {out[-200:]}")

        # Step 8: Compare regenerated artifacts
        print("\n[Phase 4] Step 8: Compare artifacts")
        comparisons = compare_artifacts(ROOT, REPRO_DIR)
        results["comparisons"] = comparisons

        # Determine pass/fail
        all_steps_ok = all(s["exit_code"] == 0 for s in results["steps"]
                          if s["step"] not in ("git_status",))
        all_comparisons_ok = all(c["match"] for c in comparisons)
        results["passed"] = all_steps_ok and all_comparisons_ok
        results["steps_passed"] = all_steps_ok
        results["comparisons_passed"] = all_comparisons_ok

        print(f"\n[Phase 4] Steps passed: {all_steps_ok}")
        print(f"[Phase 4] Comparisons passed: {all_comparisons_ok}")

    finally:
        # Save results BEFORE cleanup
        save_results(results)

        # Clean up clone
        print("\n[Phase 4] Cleaning up clone...")
        try:
            shutil.rmtree(REPRO_DIR, ignore_errors=True)
        except Exception as e:
            print(f"  Cleanup warning: {e}")

    ts_end = datetime.now(timezone.utc)
    print(f"\n[Phase 4] {'PASSED' if results['passed'] else 'FAILED'}")
    print(f"[Phase 4] Duration: {(ts_end - ts_start).total_seconds():.1f}s")
    print(f"[Phase 4] Reports: {OUT_DIR}")
    return 0 if results["passed"] else 1


def compare_artifacts(original: Path, clone: Path) -> list[dict]:
    """Compare key artifacts between original and clone."""
    comparisons = []

    # RQ3 canonical agreement
    artifacts_to_check = [
        ("generated/rq3/canonical_advisory_agreement.json", "json_semantic"),
        ("generated/rq1/rq1_comparison_summary.json", "json_semantic"),
    ]

    for rel_path, mode in artifacts_to_check:
        orig_path = original / rel_path
        clone_path = clone / rel_path

        if not orig_path.exists():
            comparisons.append({
                "artifact": rel_path,
                "match": False,
                "reason": "Original not found",
            })
            continue

        if not clone_path.exists():
            comparisons.append({
                "artifact": rel_path,
                "match": False,
                "reason": "Clone artifact not generated",
            })
            continue

        if mode == "json_semantic":
            match, detail = compare_json_semantic(orig_path, clone_path)
        else:
            match = orig_path.read_bytes() == clone_path.read_bytes()
            detail = "byte-identical" if match else "content differs"

        comparisons.append({
            "artifact": rel_path,
            "match": match,
            "reason": detail,
        })

    return comparisons


def compare_json_semantic(path_a: Path, path_b: Path) -> tuple[bool, str]:
    """Compare two JSON files semantically (ignoring timestamps, campaign IDs)."""
    try:
        a = json.loads(path_a.read_text(encoding="utf-8"))
        b = json.loads(path_b.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"Parse error: {e}"

    # Extract key metrics for comparison
    nondeterministic_keys = {"timestamp", "timestamp_start", "timestamp_end",
                             "campaign_id", "scanner_raw_dir"}

    def strip_nondeterministic(obj):
        if isinstance(obj, dict):
            return {k: strip_nondeterministic(v) for k, v in obj.items()
                    if k not in nondeterministic_keys}
        if isinstance(obj, list):
            return [strip_nondeterministic(x) for x in obj]
        return obj

    a_clean = strip_nondeterministic(a)
    b_clean = strip_nondeterministic(b)

    if a_clean == b_clean:
        return True, "Semantically equivalent (timestamps excluded)"

    # Find differences
    diffs = find_diffs(a_clean, b_clean, "")
    if not diffs:
        return True, "Semantically equivalent"
    return False, f"Differences: {'; '.join(diffs[:3])}"


def find_diffs(a, b, path: str) -> list[str]:
    """Find differences between two objects."""
    diffs = []
    if type(a) != type(b):
        diffs.append(f"{path}: type {type(a).__name__} vs {type(b).__name__}")
        return diffs
    if isinstance(a, dict):
        for k in set(list(a.keys()) + list(b.keys())):
            if k not in a:
                diffs.append(f"{path}.{k}: missing in original")
            elif k not in b:
                diffs.append(f"{path}.{k}: missing in clone")
            else:
                diffs.extend(find_diffs(a[k], b[k], f"{path}.{k}"))
    elif isinstance(a, list):
        if len(a) != len(b):
            diffs.append(f"{path}: list length {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            diffs.extend(find_diffs(x, y, f"{path}[{i}]"))
    elif a != b:
        diffs.append(f"{path}: {a} != {b}")
    return diffs


def save_results(results: dict) -> None:
    """Save reproducibility results."""
    # JSON report
    (OUT_DIR / "clean_clone_report.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8"
    )

    # Markdown report
    md = generate_markdown(results)
    (OUT_DIR / "clean_clone_report.md").write_text(md, encoding="utf-8")

    # Comparison CSV
    if results.get("comparisons"):
        import csv
        csv_path = OUT_DIR / "artifact_comparison.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["artifact", "match", "reason"])
            w.writeheader()
            w.writerows(results["comparisons"])


def generate_markdown(results: dict) -> str:
    """Generate clean_clone_report.md."""
    status = "PASSED" if results.get("passed") else "FAILED"
    lines = [
        "# Clean-Clone Reproducibility Report",
        "",
        f"**Status:** {status}",
        f"**Timestamp:** {results.get('timestamp', 'N/A')}",
        f"**Clone directory:** `{results.get('clone_dir', 'N/A')}`",
        "",
        "## Steps",
        "",
        "| Step | Exit Code | Elapsed |",
        "|------|-----------|---------|",
    ]
    for s in results.get("steps", []):
        elapsed = s.get('elapsed', 'N/A')
        elapsed_str = f"{elapsed:.1f}s" if isinstance(elapsed, (int, float)) else str(elapsed)
        lines.append(f"| {s['step']} | {s['exit_code']} | {elapsed_str} |")

    lines.extend([
        "",
        "## Artifact Comparisons",
        "",
        "| Artifact | Match | Reason |",
        "|----------|-------|--------|",
    ])
    for c in results.get("comparisons", []):
        match_str = "Yes" if c["match"] else "No"
        lines.append(f"| {c['artifact']} | {match_str} | {c['reason']} |")

    lines.extend([
        "",
        "## Nondeterministic Fields",
        "",
        "The following fields are expected to differ between runs:",
        "- `timestamp`, `timestamp_start`, `timestamp_end` (execution time)",
        "- `campaign_id` (random UUID component)",
        "- `scanner_raw_dir` (absolute path differs between machines)",
        "",
        "These are excluded from semantic comparison.",
    ])

    if results.get("failure_reason"):
        lines.extend([
            "",
            f"## Failure Reason",
            "",
            results["failure_reason"],
        ])

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
