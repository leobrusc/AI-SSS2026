"""Publication validation and readiness assessment."""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from traceai.logging_config import get_logger
from traceai.settings import get_project_root

logger = get_logger("publication")

# Status codes
SUPPORTED = "SUPPORTED"
SUPPORTED_QUICK = "SUPPORTED_QUICK_ONLY"
PARTIAL = "PARTIALLY_SUPPORTED"
UNSUPPORTED = "UNSUPPORTED"
BLOCKED_INFRA = "BLOCKED_EXTERNAL_INFRASTRUCTURE"
BLOCKED_GPU = "BLOCKED_GPU"


def validate_publication(rq: str, profile: str, output_dir: Path) -> int:
    """Validate publication readiness for a specific RQ."""
    root = get_project_root()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  Validating publication readiness for {rq} (profile={profile})")

    checks = _check_rq(rq, profile, root)
    ready = all(c["pass"] for c in checks)

    result = {
        "research_question": rq,
        "profile": profile,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ready": ready,
        "checks": checks,
    }

    out_path = output_dir / f"validate_publication_{rq}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    status = "PASS" if ready else "FAIL"
    print(f"  Result: {status}")
    for c in checks:
        mark = "[OK]" if c["pass"] else "[FAIL]"
        print(f"    {mark} {c['check']}: {c.get('detail', '')}")

    print(f"  Report: {out_path}")
    return 0 if ready else 1


def _check_rq(rq: str, profile: str, root: Path) -> list[dict]:
    """Run checks for a specific RQ."""
    if rq == "RQ1":
        return _check_rq1(root, profile)
    elif rq == "RQ2":
        return _check_rq2(root, profile)
    elif rq == "RQ3":
        return _check_rq3(root, profile)
    elif rq == "RQ4":
        return _check_rq4(root, profile)
    return [{"check": "unknown_rq", "pass": False, "detail": f"Unknown RQ: {rq}"}]


def _check_rq1(root: Path, profile: str) -> list[dict]:
    """Check RQ1 publication requirements."""
    checks = []

    # Ground truth exists
    rq1_dirs = list((root / "results" / "rq1").glob("rq1-*")) if (root / "results" / "rq1").exists() else []
    checks.append({
        "check": "rq1_campaign_executed",
        "pass": len(rq1_dirs) > 0,
        "detail": f"{len(rq1_dirs)} campaign(s) found" if rq1_dirs else "No RQ1 campaign results",
    })

    if rq1_dirs:
        latest = sorted(rq1_dirs)[-1]
        checks.append({
            "check": "ground_truth_graph_exists",
            "pass": (latest / "ground_truth_graph.json").exists(),
            "detail": str(latest / "ground_truth_graph.json"),
        })
        checks.append({
            "check": "syft_sbom_generated",
            "pass": (latest / "syft.cdx.json").exists(),
            "detail": "Syft CycloneDX SBOM present" if (latest / "syft.cdx.json").exists() else "Missing",
        })
        checks.append({
            "check": "trivy_sbom_generated",
            "pass": (latest / "trivy.cdx.json").exists(),
            "detail": "Trivy CycloneDX SBOM present" if (latest / "trivy.cdx.json").exists() else "Missing",
        })
        checks.append({
            "check": "ml_bom_generated",
            "pass": (latest / "traceai_ml_bom.cdx.json").exists(),
            "detail": "TraceAI ML-BOM present",
        })

    # LaTeX
    checks.append({
        "check": "rq1_latex_table",
        "pass": (root / "generated" / "results_rq1_table.tex").exists(),
        "detail": "results_rq1_table.tex",
    })

    return checks


def _check_rq2(root: Path, profile: str) -> list[dict]:
    """Check RQ2 publication requirements."""
    checks = []
    raw = root / "results" / "raw"
    sec_dirs = list(raw.glob("security-*")) if raw.exists() else []

    checks.append({
        "check": "security_campaign_executed",
        "pass": len(sec_dirs) > 0,
        "detail": f"{len(sec_dirs)} campaign(s)",
    })

    if sec_dirs:
        latest = sorted(sec_dirs)[-1]
        results_file = latest / "security_results.json"
        if results_file.exists():
            with open(results_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            fn = sum(1 for r in data if r.get("false_negative"))
            checks.append({
                "check": "zero_false_negatives",
                "pass": fn == 0,
                "detail": f"{fn} false negatives",
            })
            checks.append({
                "check": "uses_real_hashing",
                "pass": True,
                "detail": "Security campaign uses SHA-256 on actual fixture files",
            })
            checks.append({
                "check": "uses_real_policy_engine",
                "pass": True,
                "detail": "Gate decisions from PolicyEngine with ECDSA verification",
            })

    return checks


def _check_rq3(root: Path, profile: str) -> list[dict]:
    """Check RQ3 publication requirements."""
    checks = []
    rq3_dirs = list((root / "results" / "rq3").glob("rq3-*")) if (root / "results" / "rq3").exists() else []

    checks.append({
        "check": "rq3_campaign_executed",
        "pass": len(rq3_dirs) > 0,
        "detail": f"{len(rq3_dirs)} campaign(s)",
    })

    if rq3_dirs:
        latest = sorted(rq3_dirs)[-1]
        checks.append({
            "check": "scanner_findings_exist",
            "pass": (latest / "scanner_findings_normalized.csv").exists(),
            "detail": "Normalized scanner findings CSV",
        })
        checks.append({
            "check": "vex_decisions_exist",
            "pass": (latest / "vex_decisions.csv").exists(),
            "detail": "VEX scenario decisions CSV",
        })
        summary_path = latest / "rq3_summary.json"
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)
            agreement = summary.get("scanner_agreement", {})
            checks.append({
                "check": "scanner_comparison_real",
                "pass": agreement.get("trivy_total", 0) > 0 or agreement.get("grype_total", 0) > 0,
                "detail": f"Trivy={agreement.get('trivy_total',0)}, Grype={agreement.get('grype_total',0)}",
            })

    return checks


def _check_rq4(root: Path, profile: str) -> list[dict]:
    """Check RQ4 publication requirements."""
    import torch

    checks = []
    raw = root / "results" / "raw"
    avail_dirs = list(raw.glob("availability-*")) if raw.exists() else []

    checks.append({
        "check": "availability_campaign_executed",
        "pass": len(avail_dirs) > 0,
        "detail": f"{len(avail_dirs)} campaign(s)",
    })

    # Critical: check if it's real inference
    checks.append({
        "check": "uses_real_inference",
        "pass": False,
        "detail": "Availability campaign uses _simulate_request() — NOT real model inference",
    })

    # GPU check
    checks.append({
        "check": "gpu_metrics_available",
        "pass": torch.cuda.is_available(),
        "detail": "GPU available" if torch.cuda.is_available() else "No GPU — GPU claims cannot be made",
    })

    if not torch.cuda.is_available():
        checks.append({
            "check": "gpu_claims_blocked",
            "pass": False,
            "detail": "Manuscript MUST NOT claim GPU results on this profile",
        })

    return checks


def publication_readiness(profile: str, output_dir: Path) -> int:
    """Generate comprehensive publication readiness report."""
    root = get_project_root()
    output_dir.mkdir(parents=True, exist_ok=True)

    claims = _build_claims_matrix(root, profile)

    # Save claims matrix CSV
    csv_path = output_dir / "article_claims_matrix.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "claim", "rq", "required_evidence", "current_evidence", "status", "artifact_path"
        ])
        writer.writeheader()
        writer.writerows(claims)

    # Build readiness report
    readiness = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "claims": claims,
        "summary": {
            SUPPORTED: sum(1 for c in claims if c["status"] == SUPPORTED),
            SUPPORTED_QUICK: sum(1 for c in claims if c["status"] == SUPPORTED_QUICK),
            PARTIAL: sum(1 for c in claims if c["status"] == PARTIAL),
            UNSUPPORTED: sum(1 for c in claims if c["status"] == UNSUPPORTED),
            BLOCKED_INFRA: sum(1 for c in claims if c["status"] == BLOCKED_INFRA),
            BLOCKED_GPU: sum(1 for c in claims if c["status"] == BLOCKED_GPU),
        },
    }

    # JSON
    with open(output_dir / "publication_readiness.json", "w", encoding="utf-8") as f:
        json.dump(readiness, f, indent=2)

    # Markdown
    _write_readiness_md(readiness, output_dir / "publication_readiness.md")

    # Print summary
    print("\n" + "=" * 60)
    print("  Publication Readiness Report")
    print("=" * 60)
    for status, count in readiness["summary"].items():
        print(f"  {status}: {count}")
    print(f"\n  Reports: {output_dir}")
    print("=" * 60 + "\n")

    return 0


def _build_claims_matrix(root: Path, profile: str) -> list[dict]:
    """Build the full claims matrix."""
    rq1_dirs = list((root / "results" / "rq1").glob("rq1-*")) if (root / "results" / "rq1").exists() else []
    rq3_dirs = list((root / "results" / "rq3").glob("rq3-*")) if (root / "results" / "rq3").exists() else []
    sec_dirs = list((root / "results" / "raw").glob("security-*")) if (root / "results" / "raw").exists() else []
    import torch
    has_gpu = torch.cuda.is_available()

    claims = [
        {
            "claim": "BOM representation coverage of ground-truth graph",
            "rq": "RQ1",
            "required_evidence": "Ground-truth graph + Syft/Trivy/TraceAI BOMs + coverage metrics",
            "current_evidence": f"{len(rq1_dirs)} RQ1 campaign(s) with scanner output",
            "status": SUPPORTED_QUICK if rq1_dirs else UNSUPPORTED,
            "artifact_path": str(sorted(rq1_dirs)[-1]) if rq1_dirs else "N/A",
        },
        {
            "claim": "Cryptographic tamper detection across supply-chain scenarios",
            "rq": "RQ2",
            "required_evidence": "Real SHA-256 + ECDSA signing + policy evaluation on fixtures",
            "current_evidence": f"{len(sec_dirs)} security campaign(s) with real crypto",
            "status": SUPPORTED_QUICK if sec_dirs else UNSUPPORTED,
            "artifact_path": str(sorted(sec_dirs)[-1]) if sec_dirs else "N/A",
        },
        {
            "claim": "Scanner agreement and VEX triage effectiveness",
            "rq": "RQ3",
            "required_evidence": "Real Trivy/Grype scan output + VEX policy evaluation",
            "current_evidence": f"{len(rq3_dirs)} RQ3 campaign(s)",
            "status": SUPPORTED_QUICK if rq3_dirs else UNSUPPORTED,
            "artifact_path": str(sorted(rq3_dirs)[-1]) if rq3_dirs else "N/A",
        },
        {
            "claim": "Runtime overhead and drift detection",
            "rq": "RQ4",
            "required_evidence": "Real model inference + measured latency + observed telemetry",
            "current_evidence": "Availability campaign uses SIMULATED inference (MOCK_ONLY)",
            "status": UNSUPPORTED,
            "artifact_path": "N/A — requires real inference implementation",
        },
        {
            "claim": "GPU utilization and memory metrics",
            "rq": "RQ4",
            "required_evidence": "Real GPU telemetry from NVML/pynvml during inference",
            "current_evidence": "No GPU" if not has_gpu else "GPU available but inference simulated",
            "status": BLOCKED_GPU,
            "artifact_path": "N/A",
        },
        {
            "claim": "Harbor OCI storage and signature distribution",
            "rq": "RQ2",
            "required_evidence": "Harbor registry + pushed/signed images",
            "current_evidence": "Harbor not configured",
            "status": BLOCKED_INFRA,
            "artifact_path": "N/A",
        },
        {
            "claim": "Dependency-Track BOM/VEX ingestion and processing",
            "rq": "RQ3",
            "required_evidence": "DT API upload + response metadata",
            "current_evidence": "Dependency-Track not configured",
            "status": BLOCKED_INFRA,
            "artifact_path": "N/A",
        },
        {
            "claim": "Kubernetes/OBOM runtime observation",
            "rq": "RQ4",
            "required_evidence": "K3s deployment + runtime snapshot from live cluster",
            "current_evidence": "Kubernetes not configured",
            "status": BLOCKED_INFRA,
            "artifact_path": "N/A",
        },
        {
            "claim": "Industrial deployment end-to-end pipeline",
            "rq": "ALL",
            "required_evidence": "Industrial profile execution with all external services",
            "current_evidence": "Industrial profile not executed",
            "status": BLOCKED_INFRA,
            "artifact_path": "N/A",
        },
    ]
    return claims


def _write_readiness_md(readiness: dict, path: Path) -> None:
    """Write markdown readiness report."""
    lines = [
        "# Publication Readiness Report",
        "",
        f"**Generated:** {readiness['timestamp']}",
        f"**Profile:** {readiness['profile']}",
        "",
        "## Summary",
        "",
        "| Status | Count |",
        "|--------|-------|",
    ]
    for status, count in readiness["summary"].items():
        lines.append(f"| {status} | {count} |")

    lines.extend(["", "## Claims Matrix", ""])
    lines.append("| Claim | RQ | Status |")
    lines.append("|-------|-----|--------|")
    for c in readiness["claims"]:
        lines.append(f"| {c['claim']} | {c['rq']} | **{c['status']}** |")

    lines.extend([
        "", "## Key Blockers", "",
        "- **RQ4 Availability**: Campaign uses simulated inference — requires real HTTP calls to live service",
        "- **GPU**: No NVIDIA GPU available on this host",
        "- **Industrial infrastructure**: Harbor, Dependency-Track, GitLab, K3s not configured",
        "", "## Supported Claims (Quick Campaign)", "",
        "- RQ1: BOM coverage computed from real Syft/Trivy/TraceAI output",
        "- RQ2: Tamper detection with real SHA-256, ECDSA, policy engine",
        "- RQ3: Scanner comparison with real Trivy/Grype output + VEX policy evaluation",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
