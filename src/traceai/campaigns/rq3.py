"""RQ3 Vulnerability and VEX Campaign.

Scanner comparison (Trivy vs Grype), controlled vulnerable fixture,
and VEX scenario evaluation (V0-V7).
"""

import csv
import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from traceai.hashing import hash_file, hash_json
from traceai.logging_config import get_logger
from traceai.models import GateDecision
from traceai.settings import get_project_root, load_profile_config

logger = get_logger("campaigns.rq3")


def run_rq3_campaign(profile: str = "local", quick: bool = False, output_dir: Path = Path("results")) -> int:
    """Run RQ3 vulnerability/VEX campaign."""
    root = get_project_root()
    campaign_id = f"rq3-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    result_dir = output_dir / "rq3" / campaign_id
    raw_dir = result_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  RQ3 Campaign: {campaign_id}")
    print(f"  Profile: {profile}, Quick: {quick}")

    # 1. Create vulnerable fixture SBOM
    fixture_sbom = _create_vulnerable_fixture(root, result_dir)

    # 2. Scan with Trivy
    trivy_findings = _scan_with_trivy(fixture_sbom, raw_dir)

    # 3. Scan with Grype
    grype_findings = _scan_with_grype(fixture_sbom, raw_dir)

    # 4. Normalize and compare
    normalized, agreement = _normalize_and_compare(trivy_findings, grype_findings, result_dir)

    # 5. Run VEX scenarios
    vex_results = _run_vex_scenarios(normalized, root, result_dir)

    # 6. Save results and generate LaTeX
    _save_rq3_results(normalized, agreement, vex_results, result_dir,
                      campaign_id, profile, quick, root)

    print(f"\n  Results: {result_dir}")
    print(f"  Trivy findings: {len(trivy_findings)}")
    print(f"  Grype findings: {len(grype_findings)}")
    if agreement:
        print(f"  Jaccard similarity: {agreement.get('jaccard_similarity', 'N/A')}")
    print(f"  VEX scenarios evaluated: {len(vex_results)}")

    return 0


def _find_tool(name: str) -> Optional[str]:
    root = get_project_root()
    local = root / ".tools" / "bin" / f"{name}.exe"
    if local.exists():
        return str(local)
    return shutil.which(name)


def _create_vulnerable_fixture(root: Path, result_dir: Path) -> Path:
    """Create a static CycloneDX SBOM fixture containing known-vulnerable packages.

    This does NOT install any vulnerable packages. It is a static manifest
    that scanners can evaluate against their vulnerability databases.
    """
    fixture_dir = root / "fixtures" / "vulnerable_project"
    fixture_dir.mkdir(parents=True, exist_ok=True)

    # Create a CycloneDX SBOM with packages known to have vulnerabilities
    # These are real package versions with real CVEs that scanners should detect
    fixture_sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": {"components": [{"name": "traceai-fixture-generator", "version": "0.1.0"}]},
            "component": {
                "type": "application",
                "name": "vulnerable-fixture",
                "version": "1.0.0",
                "bom-ref": "fixture-root",
            },
        },
        "components": [
            {
                "type": "library",
                "name": "pillow",
                "version": "9.0.0",
                "purl": "pkg:pypi/pillow@9.0.0",
                "bom-ref": "comp-pillow",
            },
            {
                "type": "library",
                "name": "requests",
                "version": "2.25.0",
                "purl": "pkg:pypi/requests@2.25.0",
                "bom-ref": "comp-requests",
            },
            {
                "type": "library",
                "name": "urllib3",
                "version": "1.26.4",
                "purl": "pkg:pypi/urllib3@1.26.4",
                "bom-ref": "comp-urllib3",
            },
            {
                "type": "library",
                "name": "cryptography",
                "version": "39.0.0",
                "purl": "pkg:pypi/cryptography@39.0.0",
                "bom-ref": "comp-cryptography",
            },
            {
                "type": "library",
                "name": "setuptools",
                "version": "65.0.0",
                "purl": "pkg:pypi/setuptools@65.0.0",
                "bom-ref": "comp-setuptools",
            },
            {
                "type": "library",
                "name": "certifi",
                "version": "2022.9.24",
                "purl": "pkg:pypi/certifi@2022.9.24",
                "bom-ref": "comp-certifi",
            },
        ],
    }

    sbom_path = fixture_dir / "vulnerable_sbom.cdx.json"
    with open(sbom_path, "w", encoding="utf-8") as f:
        json.dump(fixture_sbom, f, indent=2)

    # Also save in result dir
    shutil.copy2(sbom_path, result_dir / "raw" / "fixture_sbom.cdx.json")

    return sbom_path


def _scan_with_trivy(sbom_path: Path, raw_dir: Path) -> list[dict]:
    """Scan SBOM with Trivy and return normalized findings."""
    trivy = _find_tool("trivy")
    if not trivy:
        logger.warning("Trivy not installed - scanner comparison incomplete")
        return []

    out_path = raw_dir / "trivy_scan_results.json"
    try:
        cmd = [trivy, "sbom", str(sbom_path), "--format", "json", "--output", str(out_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if not out_path.exists():
            logger.warning(f"Trivy scan produced no output: {proc.stderr[:300]}")
            return []
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _parse_trivy_findings(data)
    except Exception as e:
        logger.warning(f"Trivy scan failed: {e}")
        return []


def _scan_with_grype(sbom_path: Path, raw_dir: Path) -> list[dict]:
    """Scan SBOM with Grype and return normalized findings."""
    grype = _find_tool("grype")
    if not grype:
        logger.warning("Grype not installed - scanner comparison incomplete")
        return []

    out_path = raw_dir / "grype_scan_results.json"
    try:
        cmd = [grype, f"sbom:{sbom_path}", "-o", "json", "--file", str(out_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if not out_path.exists():
            logger.warning(f"Grype scan produced no output: {proc.stderr[:300]}")
            return []
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return _parse_grype_findings(data)
    except Exception as e:
        logger.warning(f"Grype scan failed: {e}")
        return []


def _parse_trivy_findings(data: dict) -> list[dict]:
    """Parse Trivy JSON output into normalized findings."""
    findings = []
    for result in data.get("Results", []):
        for vuln in result.get("Vulnerabilities", []):
            findings.append({
                "vulnerability_id": vuln.get("VulnerabilityID", ""),
                "package_name": vuln.get("PkgName", ""),
                "installed_version": vuln.get("InstalledVersion", ""),
                "severity": vuln.get("Severity", "UNKNOWN").upper(),
                "fix_version": vuln.get("FixedVersion", ""),
                "scanner": "trivy",
                "purl": vuln.get("PkgIdentifier", {}).get("PURL", ""),
            })
    return findings


def _parse_grype_findings(data: dict) -> list[dict]:
    """Parse Grype JSON output into normalized findings."""
    findings = []
    for match in data.get("matches", []):
        vuln = match.get("vulnerability", {})
        artifact = match.get("artifact", {})
        fix_versions = vuln.get("fix", {}).get("versions", [])
        findings.append({
            "vulnerability_id": vuln.get("id", ""),
            "package_name": artifact.get("name", ""),
            "installed_version": artifact.get("version", ""),
            "severity": vuln.get("severity", "Unknown").upper(),
            "fix_version": fix_versions[0] if fix_versions else "",
            "scanner": "grype",
            "purl": artifact.get("purl", ""),
        })
    return findings


def _normalize_and_compare(trivy_findings, grype_findings, result_dir) -> tuple[list, dict]:
    """Normalize findings and compute scanner agreement."""
    all_normalized = trivy_findings + grype_findings

    # Save normalized CSV
    csv_path = result_dir / "scanner_findings_normalized.csv"
    if all_normalized:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=all_normalized[0].keys())
            writer.writeheader()
            writer.writerows(all_normalized)

    # Compute agreement
    trivy_ids = {(f["vulnerability_id"], f["package_name"]) for f in trivy_findings}
    grype_ids = {(f["vulnerability_id"], f["package_name"]) for f in grype_findings}

    intersection = trivy_ids & grype_ids
    union = trivy_ids | grype_ids
    jaccard = round(len(intersection) / len(union), 4) if union else 0.0

    agreement = {
        "trivy_total": len(trivy_ids),
        "grype_total": len(grype_ids),
        "intersection": len(intersection),
        "union": len(union),
        "jaccard_similarity": jaccard,
        "trivy_only": len(trivy_ids - grype_ids),
        "grype_only": len(grype_ids - trivy_ids),
        "trivy_only_findings": sorted([f"{v}:{p}" for v, p in (trivy_ids - grype_ids)]),
        "grype_only_findings": sorted([f"{v}:{p}" for v, p in (grype_ids - trivy_ids)]),
    }

    # Save agreement CSV
    agree_path = result_dir / "scanner_agreement.csv"
    with open(agree_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        for k, v in agreement.items():
            if not isinstance(v, list):
                writer.writerow([k, v])

    return all_normalized, agreement


def _run_vex_scenarios(findings: list, root: Path, result_dir: Path) -> list[dict]:
    """Run VEX scenarios V0-V7."""
    from traceai.policy.engine import PolicyEngine

    policy = PolicyEngine()
    results = []

    # Pick a finding to use as target (first available, or synthetic)
    target_vuln = None
    target_component = None
    if findings:
        target_vuln = findings[0]["vulnerability_id"]
        target_component = findings[0]["package_name"]
    else:
        target_vuln = "CVE-2023-FIXTURE"
        target_component = "pillow"

    target_bom_ref = f"comp-{target_component}"

    scenarios = [
        ("V0", "no_vex", None),
        ("V1", "valid_not_affected", _make_vex_not_affected(target_vuln, target_bom_ref)),
        ("V2", "wrong_component", _make_vex_wrong_component(target_vuln)),
        ("V3", "unsigned_vex", _make_vex_unsigned(target_vuln, target_bom_ref)),
        ("V4", "expired_vex", _make_vex_expired(target_vuln, target_bom_ref)),
        ("V5", "under_investigation", _make_vex_under_investigation(target_vuln, target_bom_ref)),
        ("V6", "affected", _make_vex_affected(target_vuln, target_bom_ref)),
        ("V7", "fixed_inconsistent", _make_vex_fixed_inconsistent(target_vuln, target_bom_ref)),
    ]

    for scenario_id, name, vex_doc in scenarios:
        start = time.time()
        result = _evaluate_vex_scenario(
            scenario_id, name, vex_doc, target_vuln, target_bom_ref, policy
        )
        result["latency_ms"] = round((time.time() - start) * 1000, 3)
        results.append(result)

    # Save VEX decisions CSV
    csv_path = result_dir / "vex_decisions.csv"
    if results:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)

    return results


def _evaluate_vex_scenario(scenario_id, name, vex_doc, target_vuln, target_bom_ref, policy):
    """Evaluate a single VEX scenario."""
    result = {
        "scenario_id": scenario_id,
        "scenario_name": name,
        "vulnerability_id": target_vuln,
        "target_component": target_bom_ref,
        "vex_status": "N/A",
        "component_linkage": "N/A",
        "signature_state": "N/A",
        "expiration_state": "N/A",
        "policy_decision": "",
        "reason_code": "",
        "false_positive": False,
        "false_negative": False,
    }

    if vex_doc is None:
        # V0: no VEX — finding remains active
        result["vex_status"] = "no_vex"
        result["policy_decision"] = "FINDING_ACTIVE"
        result["reason_code"] = "No VEX provided"
        return result

    # Extract analysis from VEX
    vulns = vex_doc.get("vulnerabilities", [])
    vex_state = ""
    component_match = False
    if vulns:
        analysis = vulns[0].get("analysis", {})
        vex_state = analysis.get("state", "")
        affects = vulns[0].get("affects", [])
        component_match = any(a.get("ref") == target_bom_ref for a in affects)

    result["vex_status"] = vex_state
    result["component_linkage"] = "correct" if component_match else "wrong"
    result["signature_state"] = "unsigned"  # Local profile doesn't require VEX signing
    result["expiration_state"] = "valid"

    # Check expiry
    metadata = vex_doc.get("metadata", {})
    for prop in metadata.get("properties", []):
        if prop.get("name") == "traceai:expires":
            try:
                exp = datetime.fromisoformat(prop["value"])
                if datetime.now(timezone.utc) > exp:
                    result["expiration_state"] = "expired"
            except (ValueError, KeyError):
                pass

    # Policy evaluation
    is_expired = result["expiration_state"] == "expired"
    is_valid_schema = vex_doc.get("bomFormat") == "CycloneDX"

    evaluation = policy.evaluate_vex(
        vex_document=vex_doc,
        vex_signed=False,
        vex_expired=is_expired,
        vex_component_match=component_match,
        vex_schema_valid=is_valid_schema,
    )

    result["policy_decision"] = evaluation.decision.value
    result["reason_code"] = evaluation.reason

    # Determine FP/FN based on expected outcomes
    expected = {
        "V1": GateDecision.APPROVED,  # Valid not_affected should suppress
        "V2": GateDecision.VEX_WRONG_COMPONENT,
        "V3": GateDecision.APPROVED,  # Local profile doesn't require VEX signing
        "V4": GateDecision.VEX_EXPIRED,
        "V5": GateDecision.APPROVED,  # under_investigation is informational
        "V6": GateDecision.APPROVED,  # affected is informational, doesn't mean gate fails
        "V7": GateDecision.APPROVED,  # fixed is informational
    }
    expected_decision = expected.get(scenario_id)
    if expected_decision:
        if evaluation.decision != expected_decision:
            if evaluation.decision == GateDecision.APPROVED and expected_decision != GateDecision.APPROVED:
                result["false_negative"] = True
            elif evaluation.decision != GateDecision.APPROVED and expected_decision == GateDecision.APPROVED:
                result["false_positive"] = True

    return result


# VEX document generators

def _make_vex_not_affected(vuln_id, bom_ref):
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "vulnerabilities": [{
            "id": vuln_id,
            "analysis": {"state": "not_affected", "justification": "code_not_reachable",
                         "detail": "Controlled test fixture"},
            "affects": [{"ref": bom_ref}],
        }],
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "properties": []},
    }

def _make_vex_wrong_component(vuln_id):
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "vulnerabilities": [{
            "id": vuln_id,
            "analysis": {"state": "not_affected", "justification": "code_not_reachable"},
            "affects": [{"ref": "comp-WRONG-COMPONENT"}],
        }],
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "properties": []},
    }

def _make_vex_unsigned(vuln_id, bom_ref):
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "vulnerabilities": [{
            "id": vuln_id,
            "analysis": {"state": "not_affected", "justification": "code_not_reachable"},
            "affects": [{"ref": bom_ref}],
        }],
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "properties": []},
    }

def _make_vex_expired(vuln_id, bom_ref):
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "vulnerabilities": [{
            "id": vuln_id,
            "analysis": {"state": "not_affected", "justification": "code_not_reachable"},
            "affects": [{"ref": bom_ref}],
        }],
        "metadata": {
            "timestamp": "2023-01-01T00:00:00Z",
            "properties": [{"name": "traceai:expires", "value": "2023-06-01T00:00:00+00:00"}],
        },
    }

def _make_vex_under_investigation(vuln_id, bom_ref):
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "vulnerabilities": [{
            "id": vuln_id,
            "analysis": {"state": "under_investigation"},
            "affects": [{"ref": bom_ref}],
        }],
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "properties": []},
    }

def _make_vex_affected(vuln_id, bom_ref):
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "vulnerabilities": [{
            "id": vuln_id,
            "analysis": {"state": "affected", "response": ["workaround_available"]},
            "affects": [{"ref": bom_ref}],
        }],
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "properties": []},
    }

def _make_vex_fixed_inconsistent(vuln_id, bom_ref):
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "vulnerabilities": [{
            "id": vuln_id,
            "analysis": {"state": "fixed", "detail": "Fixed in 10.0.0 but 9.0.0 installed"},
            "affects": [{"ref": bom_ref}],
        }],
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "properties": []},
    }


def _save_rq3_results(normalized, agreement, vex_results, result_dir,
                       campaign_id, profile, quick, root):
    """Save all RQ3 results and generate LaTeX."""
    # Summary JSON
    summary = {
        "campaign_id": campaign_id,
        "profile": profile,
        "quick": quick,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scanner_agreement": agreement,
        "vex_scenario_count": len(vex_results),
        "vex_false_positives": sum(1 for v in vex_results if v.get("false_positive")),
        "vex_false_negatives": sum(1 for v in vex_results if v.get("false_negative")),
    }
    with open(result_dir / "rq3_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Generate LaTeX
    gen_dir = root / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)
    from traceai.environment import escape_latex

    # Scanner agreement table
    lines = [
        r"\begin{table}[htbp]",
        r"\caption{Scanner Agreement (RQ3 -- Diagnostic)}",
        r"\label{tab:scanner-agreement}",
        r"\centering\small",
        r"\begin{tabular}{lr}",
        r"\toprule",
        r"\textbf{Metric} & \textbf{Value} \\",
        r"\midrule",
    ]
    if agreement:
        for k in ["trivy_total", "grype_total", "intersection", "jaccard_similarity",
                  "trivy_only", "grype_only"]:
            lines.append(f"  {escape_latex(k)} & {agreement.get(k, 'N/A')} \\\\")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    (gen_dir / "results_scanner_agreement_table.tex").write_text("\n".join(lines), encoding="utf-8")

    # VEX table
    vex_lines = [
        r"\begin{table}[htbp]",
        r"\caption{VEX Scenario Results (RQ3 -- Diagnostic)}",
        r"\label{tab:vex-scenarios}",
        r"\centering\small",
        r"\begin{tabular}{llll}",
        r"\toprule",
        r"\textbf{ID} & \textbf{Scenario} & \textbf{Decision} & \textbf{FP/FN} \\",
        r"\midrule",
    ]
    for v in vex_results:
        fp_fn = ""
        if v.get("false_positive"):
            fp_fn = "FP"
        elif v.get("false_negative"):
            fp_fn = "FN"
        vex_lines.append(
            f"  {v['scenario_id']} & {escape_latex(v['scenario_name'])} & "
            f"{escape_latex(v['policy_decision'])} & {fp_fn} \\\\"
        )
    vex_lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    (gen_dir / "results_vex_table.tex").write_text("\n".join(vex_lines), encoding="utf-8")

    # RQ3 combined table
    (gen_dir / "results_rq3_table.tex").write_text(
        "% See results_scanner_agreement_table.tex and results_vex_table.tex\n"
        r"\input{results_scanner_agreement_table}" + "\n"
        r"\input{results_vex_table}",
        encoding="utf-8",
    )

    # Summary tex
    rq3_summary = [
        f"% RQ3 Summary (quick/diagnostic) Campaign: {campaign_id}",
        r"\paragraph{RQ3 Vulnerability and VEX Evaluation}",
    ]
    if agreement:
        rq3_summary.append(
            f"Trivy identified {agreement['trivy_total']} findings; "
            f"Grype identified {agreement['grype_total']} findings "
            f"(Jaccard: {agreement['jaccard_similarity']}). "
        )
    rq3_summary.append(
        f"VEX evaluation across {len(vex_results)} scenarios: "
        f"{summary['vex_false_positives']} FP, {summary['vex_false_negatives']} FN."
    )
    (gen_dir / "results_rq3_summary.tex").write_text("\n".join(rq3_summary), encoding="utf-8")
