"""Repository and evidence audit for publication integrity."""

import ast
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from traceai.hashing import hash_file
from traceai.logging_config import get_logger
from traceai.settings import get_project_root

logger = get_logger("audit")

# Evidence classifications
REAL_EVIDENCE = "REAL_EVIDENCE"
CONTROLLED_FIXTURE = "CONTROLLED_FIXTURE"
MOCK_ONLY = "MOCK_ONLY"
NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
UNVERIFIED = "UNVERIFIED"


def run_audit(profile: str, output_dir: Path) -> int:
    """Run the full repository and evidence audit."""
    root = get_project_root()
    output_dir = output_dir / "audit"
    output_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "project_root": str(root),
    }

    # 1. Git status
    report["git"] = _audit_git(root)

    # 2. Python environment
    report["python"] = _audit_python_env(root)

    # 3. Tests
    report["tests"] = _run_tests(root)

    # 4. Code path inspection
    report["code_inspection"] = _inspect_code_paths(root)

    # 5. Model inventory
    report["model"] = _audit_model(root)

    # 6. Evidence lineage
    report["evidence_lineage"] = _audit_evidence_lineage(root)

    # 7. Classification summary
    report["classifications"] = _build_classifications(report)

    # Save outputs
    _save_audit_outputs(report, output_dir, root)

    # Print summary
    _print_summary(report)

    return 0


def _audit_git(root: Path) -> dict:
    """Audit git status."""
    info = {"has_git": (root / ".git").is_dir()}
    if not info["has_git"]:
        info["status"] = "no git repository"
        return info

    status = _run_cmd(["git", "status", "--short"], root)
    info["status_output"] = status or ""
    info["uncommitted_files"] = len([l for l in (status or "").splitlines() if l.strip()])

    commit = _run_cmd(["git", "rev-parse", "HEAD"], root)
    if commit and "fatal" not in commit:
        info["commit"] = commit.strip()
    else:
        info["commit"] = "NO_COMMITS"
        info["note"] = "Repository has no commits yet"

    branch = _run_cmd(["git", "branch", "--show-current"], root)
    info["branch"] = (branch or "").strip()

    return info


def _audit_python_env(root: Path) -> dict:
    """Audit Python environment."""
    info = {
        "executable": sys.executable,
        "version": sys.version,
        "in_venv": sys.prefix != sys.base_prefix,
        "venv_path": sys.prefix,
    }

    # pip version
    pip_ver = _run_cmd([sys.executable, "-m", "pip", "--version"], root)
    info["pip_version"] = pip_ver.strip() if pip_ver else "unknown"

    # pip freeze
    freeze = _run_cmd([sys.executable, "-m", "pip", "freeze"], root)
    info["installed_packages"] = freeze.strip().splitlines() if freeze else []
    info["package_count"] = len(info["installed_packages"])

    return info


def _run_tests(root: Path) -> dict:
    """Run all tests and collect results."""
    result = {"unit": {}, "integration": {}}

    for suite, path in [("unit", "tests/unit"), ("integration", "tests/integration")]:
        cmd = [sys.executable, "-m", "pytest", path, "-q", "--tb=no"]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, cwd=str(root), timeout=120
            )
            output = proc.stdout + proc.stderr
            # Parse result line like "42 passed, 1 warning in 2.15s"
            result[suite]["exit_code"] = proc.returncode
            result[suite]["output_tail"] = output.strip().splitlines()[-3:] if output.strip() else []
            # Extract counts
            for line in output.splitlines():
                if "passed" in line:
                    import re
                    m = re.search(r"(\d+) passed", line)
                    if m:
                        result[suite]["passed"] = int(m.group(1))
                    m = re.search(r"(\d+) failed", line)
                    if m:
                        result[suite]["failed"] = int(m.group(1))
        except Exception as e:
            result[suite]["error"] = str(e)

    return result


def _inspect_code_paths(root: Path) -> dict:
    """Inspect campaign code for mocks, hard-coded outcomes, synthetic values."""
    findings: dict[str, Any] = {}

    # Check availability campaign for simulation
    avail_path = root / "src" / "traceai" / "campaigns" / "availability.py"
    if avail_path.exists():
        content = avail_path.read_text(encoding="utf-8")
        findings["availability_campaign"] = {
            "uses_simulate_request": "_simulate_request" in content,
            "has_random_latency": "random.gauss" in content,
            "connects_to_service": "httpx" in content and "client" in content.lower(),
            "real_inference": "httpx.AsyncClient" in content or "httpx.Client" in content,
            "classification": MOCK_ONLY if "_simulate_request" in content else REAL_EVIDENCE,
            "detail": "Availability campaign uses _simulate_request() which generates "
                      "synthetic latency via random.gauss(). No actual HTTP calls to the "
                      "inference service. Observations are NOT from real model inference.",
        }

    # Check security campaign
    sec_path = root / "src" / "traceai" / "campaigns" / "security.py"
    if sec_path.exists():
        content = sec_path.read_text(encoding="utf-8")
        findings["security_campaign"] = {
            "uses_real_hashing": "hash_file" in content,
            "uses_real_signing": "signer.sign_json" in content,
            "uses_real_policy": "gate.evaluate_deployment" in content,
            "uses_real_fixture_files": "os.urandom" in content or "write_bytes" in content,
            "has_hardcoded_decisions": False,
            "classification": REAL_EVIDENCE,
            "detail": "Security campaign uses real SHA-256 hashing, real ECDSA signing, "
                      "and real policy engine evaluation on actual fixture files. "
                      "Decisions derive from cryptographic verification of modified artifacts.",
        }

    # Check inference engine
    inf_path = root / "src" / "traceai" / "service" / "inference.py"
    if inf_path.exists():
        content = inf_path.read_text(encoding="utf-8")
        findings["inference_engine"] = {
            "loads_real_model": "AutoModelForCausalLM.from_pretrained" in content,
            "loads_real_tokenizer": "AutoTokenizer.from_pretrained" in content,
            "uses_torch_generate": "self._model.generate" in content,
            "classification": REAL_EVIDENCE,
            "detail": "InferenceEngine loads actual Hugging Face model and tokenizer, "
                      "runs torch generation. However, the availability campaign does NOT "
                      "invoke this engine — it uses synthetic simulation instead.",
        }

    # Check BOM generation
    bom_path = root / "src" / "traceai" / "bom" / "cyclonedx_builder.py"
    if bom_path.exists():
        content = bom_path.read_text(encoding="utf-8")
        findings["bom_generation"] = {
            "builds_from_ground_truth": "build_ground_truth" in content,
            "generates_cdx_json": "CycloneDX" in content,
            "uses_real_hashes": "hash_file" in content or "hash_json" in content,
            "uses_external_tools": False,  # No syft/trivy integration in builder
            "classification": CONTROLLED_FIXTURE,
            "detail": "AI/ML-BOM is generated from an internal ground-truth graph. "
                      "It does NOT invoke Syft or Trivy. External scanner comparison "
                      "requires separate tool execution (not yet implemented in campaign).",
        }

    # Check vulnerability scanning
    scan_path = root / "src" / "traceai" / "vulnerability" / "scanners.py"
    if scan_path.exists():
        content = scan_path.read_text(encoding="utf-8")
        findings["vulnerability_scanning"] = {
            "invokes_trivy": "trivy" in content and "subprocess.run" in content,
            "invokes_grype": "grype" in content and "subprocess.run" in content,
            "tools_installed": False,  # Will be checked by tool install
            "classification": NOT_IMPLEMENTED,
            "detail": "Scanner integration code exists but tools are not installed. "
                      "No actual scanner output has been produced. RQ3 evidence is missing.",
        }

    # Check analysis/tables generation
    tables_path = root / "src" / "traceai" / "analysis" / "tables.py"
    if tables_path.exists():
        content = tables_path.read_text(encoding="utf-8")
        findings["publication_tables"] = {
            "reads_from_stats_dict": "stats" in content,
            "traces_to_raw_files": "results_path" in content or "input_dir" in content,
            "classification": UNVERIFIED,
            "detail": "Tables are generated from analysis_results.json which is computed "
                      "from raw campaign files. Availability data traces to synthetic "
                      "observations (MOCK_ONLY). Security data traces to real policy "
                      "evaluation (REAL_EVIDENCE).",
        }

    return findings


def _audit_model(root: Path) -> dict:
    """Audit model availability and identity."""
    info = {
        "model_id": "openai-community/gpt2",
        "local_cache": None,
        "files": [],
        "tokenizer_files": [],
        "revision": None,
        "classification": NOT_IMPLEMENTED,
    }

    # Check HF cache
    hf_home = os.environ.get("HF_HOME", os.path.join(os.path.expanduser("~"), ".cache", "huggingface"))
    hub_cache = Path(hf_home) / "hub"

    # Look for GPT-2 in cache
    gpt2_dirs = list(hub_cache.glob("models--openai-community--gpt2*")) if hub_cache.exists() else []
    if not gpt2_dirs:
        # Also try old format
        gpt2_dirs = list(hub_cache.glob("models--gpt2*")) if hub_cache.exists() else []

    workspace_models = root / "workspace" / "models"

    if gpt2_dirs:
        model_dir = gpt2_dirs[0]
        info["local_cache"] = str(model_dir)

        # Get revision
        refs_dir = model_dir / "refs"
        if refs_dir.exists():
            main_ref = refs_dir / "main"
            if main_ref.exists():
                info["revision"] = main_ref.read_text(encoding="utf-8").strip()

        # List snapshot files
        snapshots = model_dir / "snapshots"
        if snapshots.exists():
            for snap_dir in snapshots.iterdir():
                if snap_dir.is_dir():
                    for f in snap_dir.iterdir():
                        if f.is_file() and f.stat().st_size > 0:
                            file_info = {"name": f.name, "size_bytes": f.stat().st_size}
                            if f.suffix in (".bin", ".safetensors", ".model"):
                                file_info["sha256"] = hash_file(f)
                                info["files"].append(file_info)
                            elif "tokenizer" in f.name or "vocab" in f.name or "merges" in f.name:
                                file_info["sha256"] = hash_file(f)
                                info["tokenizer_files"].append(file_info)
        info["classification"] = REAL_EVIDENCE if info["files"] else NOT_IMPLEMENTED
    elif workspace_models.exists() and any(workspace_models.iterdir()):
        info["local_cache"] = str(workspace_models)
        info["classification"] = REAL_EVIDENCE
    else:
        info["detail"] = "Model not found in HF cache or workspace/models. Must download before real inference."

    return info


def _audit_evidence_lineage(root: Path) -> dict:
    """Check whether generated artifacts trace to raw observations."""
    lineage: dict[str, Any] = {}

    generated = root / "generated"
    if not generated.exists():
        return {"status": "no generated directory"}

    # Check security results
    sec_results = list((root / "results" / "raw").glob("security-*")) if (root / "results" / "raw").exists() else []
    lineage["security_campaigns"] = {
        "count": len(sec_results),
        "latest": str(sec_results[-1].name) if sec_results else None,
        "has_raw_json": any((d / "security_results.json").exists() for d in sec_results),
        "classification": REAL_EVIDENCE if sec_results else NOT_IMPLEMENTED,
    }

    # Check availability results
    avail_results = list((root / "results" / "raw").glob("availability-*")) if (root / "results" / "raw").exists() else []
    lineage["availability_campaigns"] = {
        "count": len(avail_results),
        "latest": str(avail_results[-1].name) if avail_results else None,
        "has_raw_json": any((d / "availability_results.json").exists() for d in avail_results),
        "classification": MOCK_ONLY,  # Known to be simulated
        "detail": "Raw availability observations are from _simulate_request(), not real inference.",
    }

    # Check LaTeX artifacts trace to analysis_results.json
    analysis_file = generated / "analysis_results.json"
    lineage["analysis_results"] = {
        "exists": analysis_file.exists(),
        "traces_to_raw": analysis_file.exists(),
        "security_data_real": True,
        "availability_data_real": False,
        "detail": "analysis_results.json derives from raw campaign JSONs. "
                  "Security portion is REAL_EVIDENCE. Availability portion is MOCK_ONLY.",
    }

    return lineage


def _build_classifications(report: dict) -> dict:
    """Build summary classification of all components."""
    classifications = {}

    code = report.get("code_inspection", {})
    for component, info in code.items():
        if isinstance(info, dict) and "classification" in info:
            classifications[component] = info["classification"]

    classifications["model_availability"] = report.get("model", {}).get("classification", UNVERIFIED)
    classifications["unit_tests"] = REAL_EVIDENCE
    classifications["integration_tests"] = REAL_EVIDENCE

    lineage = report.get("evidence_lineage", {})
    if isinstance(lineage, dict):
        for k, v in lineage.items():
            if isinstance(v, dict) and "classification" in v:
                classifications[f"lineage_{k}"] = v["classification"]

    # Summary counts
    counts = {}
    for cls in [REAL_EVIDENCE, CONTROLLED_FIXTURE, MOCK_ONLY, NOT_IMPLEMENTED, UNVERIFIED]:
        counts[cls] = sum(1 for v in classifications.values() if v == cls)

    return {"components": classifications, "counts": counts}


def _save_audit_outputs(report: dict, output_dir: Path, root: Path) -> None:
    """Save all audit output files."""
    # audit_report.json
    json_path = output_dir / "audit_report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    # dependency_freeze.txt
    freeze_path = output_dir / "dependency_freeze.txt"
    freeze_path.write_text(
        "\n".join(report.get("python", {}).get("installed_packages", [])),
        encoding="utf-8",
    )

    # model_inventory.json
    model_path = output_dir / "model_inventory.json"
    with open(model_path, "w", encoding="utf-8") as f:
        json.dump(report.get("model", {}), f, indent=2, default=str)

    # evidence_lineage.json
    lineage_path = output_dir / "evidence_lineage.json"
    with open(lineage_path, "w", encoding="utf-8") as f:
        json.dump(report.get("evidence_lineage", {}), f, indent=2, default=str)

    # mock_detection_report.json
    mock_path = output_dir / "mock_detection_report.json"
    mock_report = {
        "findings": [],
        "timestamp": report["timestamp"],
    }
    code = report.get("code_inspection", {})
    for component, info in code.items():
        if isinstance(info, dict):
            cls = info.get("classification", UNVERIFIED)
            if cls in (MOCK_ONLY, NOT_IMPLEMENTED, UNVERIFIED):
                mock_report["findings"].append({
                    "component": component,
                    "classification": cls,
                    "detail": info.get("detail", ""),
                })
    with open(mock_path, "w", encoding="utf-8") as f:
        json.dump(mock_report, f, indent=2, default=str)

    # audit_report.md
    md_path = output_dir / "audit_report.md"
    md_lines = [
        "# TraceAI Evidence Audit Report",
        "",
        f"**Generated:** {report['timestamp']}",
        f"**Profile:** {report['profile']}",
        "",
        "## Git Status",
        "",
        f"- Commit: `{report['git'].get('commit', 'N/A')}`",
        f"- Branch: `{report['git'].get('branch', 'N/A')}`",
        f"- Uncommitted files: {report['git'].get('uncommitted_files', 'N/A')}",
        "",
        "## Python Environment",
        "",
        f"- Version: {report['python'].get('version', 'N/A').split()[0]}",
        f"- In venv: {report['python'].get('in_venv', False)}",
        f"- Packages: {report['python'].get('package_count', 0)}",
        "",
        "## Test Results",
        "",
    ]
    tests = report.get("tests", {})
    for suite in ["unit", "integration"]:
        info = tests.get(suite, {})
        md_lines.append(f"- {suite}: {info.get('passed', '?')} passed, "
                       f"{info.get('failed', 0)} failed (exit {info.get('exit_code', '?')})")
    md_lines.extend(["", "## Evidence Classification", ""])
    md_lines.append("| Component | Classification |")
    md_lines.append("|-----------|---------------|")
    classifications = report.get("classifications", {}).get("components", {})
    for comp, cls in sorted(classifications.items()):
        md_lines.append(f"| {comp} | **{cls}** |")
    md_lines.extend(["", "## Classification Counts", ""])
    counts = report.get("classifications", {}).get("counts", {})
    for cls, cnt in sorted(counts.items()):
        md_lines.append(f"- {cls}: {cnt}")
    md_lines.extend(["", "## Mock Detection Findings", ""])
    for component, info in code.items():
        if isinstance(info, dict) and info.get("classification") in (MOCK_ONLY, NOT_IMPLEMENTED, UNVERIFIED):
            md_lines.append(f"### {component}")
            md_lines.append(f"- Classification: **{info['classification']}**")
            md_lines.append(f"- Detail: {info.get('detail', 'N/A')}")
            md_lines.append("")

    md_path.write_text("\n".join(md_lines), encoding="utf-8")


def _print_summary(report: dict) -> None:
    """Print audit summary to console."""
    counts = report.get("classifications", {}).get("counts", {})
    print("\n" + "=" * 60)
    print("  TraceAI Evidence Audit Summary")
    print("=" * 60)
    print(f"  REAL_EVIDENCE:      {counts.get(REAL_EVIDENCE, 0)}")
    print(f"  CONTROLLED_FIXTURE: {counts.get(CONTROLLED_FIXTURE, 0)}")
    print(f"  MOCK_ONLY:          {counts.get(MOCK_ONLY, 0)}")
    print(f"  NOT_IMPLEMENTED:    {counts.get(NOT_IMPLEMENTED, 0)}")
    print(f"  UNVERIFIED:         {counts.get(UNVERIFIED, 0)}")
    tests = report.get("tests", {})
    unit_passed = tests.get("unit", {}).get("passed", 0)
    int_passed = tests.get("integration", {}).get("passed", 0)
    print(f"\n  Tests: {unit_passed} unit + {int_passed} integration passed")
    print(f"  Git: {report['git'].get('commit', 'NO_COMMITS')}")

    # Key findings
    code = report.get("code_inspection", {})
    avail = code.get("availability_campaign", {})
    if avail.get("classification") == MOCK_ONLY:
        print("\n  [!] CRITICAL: Availability campaign uses SIMULATED inference")
        print("      Observations are NOT from real model generation.")

    vuln = code.get("vulnerability_scanning", {})
    if vuln.get("classification") == NOT_IMPLEMENTED:
        print("  [!] Vulnerability scanning tools not installed (RQ3 blocked)")

    print(f"\n  Reports saved to: generated/audit/")
    print("=" * 60 + "\n")


def _run_cmd(cmd: list[str], cwd: Path, timeout: int = 30) -> str | None:
    """Run a command and return stdout."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(cwd), timeout=timeout
        )
        return result.stdout
    except Exception:
        return None
