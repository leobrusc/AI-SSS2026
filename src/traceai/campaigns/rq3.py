"""RQ3 Scanner Agreement and VEX Policy Conformance Campaign.

Compares vulnerability scanners (Trivy vs Grype) using a controlled fixture SBOM,
computes stratified Jaccard agreement, produces a disagreement taxonomy, and
evaluates VEX policy conformance scenarios (V0-V7).
"""

import csv
import json
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
from traceai.policy.engine import PolicyEngine

logger = get_logger("campaigns.rq3")

# ---------------------------------------------------------------------------
# Canonical finding key: (canonical_advisory_id, ecosystem, canonical_purl, installed_version)
# ---------------------------------------------------------------------------

_ECOSYSTEM_PYPI = "pypi"
_ECOSYSTEM_OS = "os"

_DISAGREEMENT_CATEGORIES = (
    "advisory_alias_mismatch",
    "package_identity_mismatch",
    "version_range_interpretation",
    "database_coverage_difference",
    "severity_disagreement",
    "fix_version_disagreement",
    "duplicate_record",
    "unknown",
)


# ===========================================================================
# Public entry point
# ===========================================================================


def run_rq3_campaign(profile: str = "local", quick: bool = False, output_dir: Path = Path("results")) -> int:
    """Run RQ3 scanner agreement and VEX policy conformance campaign."""
    root = get_project_root()
    campaign_id = f"rq3-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    result_dir = output_dir / "rq3" / campaign_id
    raw_dir = result_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    gen_dir = root / "generated" / "rq3"
    gen_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  RQ3 Campaign: {campaign_id}")
    print(f"  Profile: {profile}, Quick: {quick}")

    # 1. Create vulnerable fixture SBOM
    fixture_sbom = _create_vulnerable_fixture(root, result_dir)
    target_hash = hash_file(fixture_sbom)

    # 2. Scan with Trivy
    trivy_raw, trivy_meta = _scan_with_trivy(fixture_sbom, raw_dir)

    # 3. Scan with Grype
    grype_raw, grype_meta = _scan_with_grype(fixture_sbom, raw_dir)

    # 4. Normalize findings to canonical keys
    trivy_normalized = _normalize_findings(trivy_raw, "trivy")
    grype_normalized = _normalize_findings(grype_raw, "grype")

    # 5. Deduplicate within each scanner
    trivy_deduped = _deduplicate_findings(trivy_normalized)
    grype_deduped = _deduplicate_findings(grype_normalized)

    # 6. Compute stratified Jaccard agreement
    agreement_stratified = _compute_stratified_jaccard(trivy_deduped, grype_deduped)

    # 7. Produce disagreement taxonomy
    taxonomy = _build_disagreement_taxonomy(trivy_deduped, grype_deduped, trivy_raw, grype_raw)

    # 8. Record scanner DB metadata
    db_metadata = _build_db_metadata(trivy_meta, grype_meta, target_hash)

    # 9. Run VEX policy conformance scenarios
    all_normalized = trivy_deduped + grype_deduped
    vex_results = _run_vex_scenarios(all_normalized, root, result_dir)

    # 10. Save all outputs
    _save_results_dir(trivy_deduped, grype_deduped, agreement_stratified,
                      vex_results, result_dir, campaign_id, profile, quick)
    _save_generated_dir(agreement_stratified, taxonomy, db_metadata, vex_results, gen_dir)

    # Print summary
    print(f"\n  Results: {result_dir}")
    print(f"  Generated: {gen_dir}")
    print(f"  Trivy findings (deduplicated): {len(trivy_deduped)}")
    print(f"  Grype findings (deduplicated): {len(grype_deduped)}")
    j_all = agreement_stratified["all"]["jaccard"]
    print(f"  Jaccard (all): {j_all:.4f}")
    conformance_passed = sum(1 for v in vex_results if v["conformance_passed"])
    print(f"  VEX policy conformance: {conformance_passed}/{len(vex_results)} rules passed")

    return 0


# ===========================================================================
# Tool discovery
# ===========================================================================


def _find_tool(name: str) -> Optional[str]:
    """Find a scanner binary: check .tools/bin/name.exe first, then PATH."""
    root = get_project_root()
    local_exe = root / ".tools" / "bin" / f"{name}.exe"
    if local_exe.exists():
        return str(local_exe)
    local_plain = root / ".tools" / "bin" / name
    if local_plain.exists():
        return str(local_plain)
    return shutil.which(name)


# ===========================================================================
# Fixture creation
# ===========================================================================


def _create_vulnerable_fixture(root: Path, result_dir: Path) -> Path:
    """Create a static CycloneDX SBOM fixture with known-vulnerable packages."""
    fixture_dir = root / "fixtures" / "vulnerable_project"
    fixture_dir.mkdir(parents=True, exist_ok=True)

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

    shutil.copy2(sbom_path, result_dir / "raw" / "fixture_sbom.cdx.json")
    return sbom_path



# ===========================================================================
# Scanner execution
# ===========================================================================


def _scan_with_trivy(sbom_path: Path, raw_dir: Path) -> tuple[list[dict], dict]:
    """Scan SBOM with Trivy; return (raw_findings, metadata)."""
    trivy = _find_tool("trivy")
    meta: dict[str, Any] = {"scanner": "trivy", "scan_timestamp": datetime.now(timezone.utc).isoformat()}

    if not trivy:
        logger.warning("Trivy not installed - scanner comparison incomplete")
        meta["available"] = False
        return [], meta

    # Get version
    try:
        ver_proc = subprocess.run([trivy, "version", "--format", "json"],
                                  capture_output=True, text=True, timeout=30)
        if ver_proc.returncode == 0:
            ver_data = json.loads(ver_proc.stdout)
            meta["scanner_version"] = ver_data.get("Version", "")
            # DB version from Trivy version output
            for db_info in ver_data.get("VulnerabilityDB", {}).get("UpdatedAt", ""):
                pass
            meta["db_version"] = ver_data.get("VulnerabilityDB", {}).get("Version", "")
            meta["db_updated_at"] = ver_data.get("VulnerabilityDB", {}).get("UpdatedAt", "")
    except Exception as e:
        logger.debug(f"Could not get Trivy version: {e}")
        meta["scanner_version"] = "unknown"

    out_path = raw_dir / "trivy_scan_results.json"
    try:
        cmd = [trivy, "sbom", str(sbom_path), "--format", "json", "--output", str(out_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if not out_path.exists():
            logger.warning(f"Trivy scan produced no output: {proc.stderr[:300]}")
            return [], meta
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        meta["available"] = True
        return _parse_trivy_findings(data), meta
    except Exception as e:
        logger.warning(f"Trivy scan failed: {e}")
        meta["available"] = False
        return [], meta


def _scan_with_grype(sbom_path: Path, raw_dir: Path) -> tuple[list[dict], dict]:
    """Scan SBOM with Grype; return (raw_findings, metadata)."""
    grype = _find_tool("grype")
    meta: dict[str, Any] = {"scanner": "grype", "scan_timestamp": datetime.now(timezone.utc).isoformat()}

    if not grype:
        logger.warning("Grype not installed - scanner comparison incomplete")
        meta["available"] = False
        return [], meta

    # Get version
    try:
        ver_proc = subprocess.run([grype, "version", "-o", "json"],
                                  capture_output=True, text=True, timeout=30)
        if ver_proc.returncode == 0:
            ver_data = json.loads(ver_proc.stdout)
            meta["scanner_version"] = ver_data.get("version", ver_data.get("Version", ""))
            meta["db_version"] = ver_data.get("dbStatus", {}).get("schemaVersion", "")
            meta["db_updated_at"] = ver_data.get("dbStatus", {}).get("built", "")
    except Exception as e:
        logger.debug(f"Could not get Grype version: {e}")
        meta["scanner_version"] = "unknown"

    out_path = raw_dir / "grype_scan_results.json"
    try:
        cmd = [grype, f"sbom:{sbom_path}", "-o", "json", "--file", str(out_path)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if not out_path.exists():
            logger.warning(f"Grype scan produced no output: {proc.stderr[:300]}")
            return [], meta
        with open(out_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        meta["available"] = True
        return _parse_grype_findings(data), meta
    except Exception as e:
        logger.warning(f"Grype scan failed: {e}")
        meta["available"] = False
        return [], meta


def _parse_trivy_findings(data: dict) -> list[dict]:
    """Parse Trivy JSON output into raw finding dicts."""
    findings = []
    for result in data.get("Results", []):
        for vuln in result.get("Vulnerabilities", []):
            purl = vuln.get("PkgIdentifier", {}).get("PURL", "")
            findings.append({
                "vulnerability_id": vuln.get("VulnerabilityID", ""),
                "package_name": vuln.get("PkgName", ""),
                "installed_version": vuln.get("InstalledVersion", ""),
                "severity": vuln.get("Severity", "UNKNOWN").upper(),
                "fix_version": vuln.get("FixedVersion", ""),
                "purl": purl,
                "data_source": vuln.get("DataSource", {}).get("Name", ""),
                "related_ids": vuln.get("RelatedVulnerabilities", []),
            })
    return findings


def _parse_grype_findings(data: dict) -> list[dict]:
    """Parse Grype JSON output into raw finding dicts."""
    findings = []
    for match in data.get("matches", []):
        vuln = match.get("vulnerability", {})
        artifact = match.get("artifact", {})
        fix_versions = vuln.get("fix", {}).get("versions", [])
        related = [r.get("id", "") for r in vuln.get("relatedVulnerabilities", [])]
        findings.append({
            "vulnerability_id": vuln.get("id", ""),
            "package_name": artifact.get("name", ""),
            "installed_version": artifact.get("version", ""),
            "severity": vuln.get("severity", "Unknown").upper(),
            "fix_version": fix_versions[0] if fix_versions else "",
            "purl": artifact.get("purl", ""),
            "data_source": vuln.get("dataSource", ""),
            "related_ids": related,
        })
    return findings



# ===========================================================================
# Normalization and deduplication
# ===========================================================================


def _canonical_purl(purl: str, package_name: str) -> str:
    """Normalize a purl to canonical form: pkg:<ecosystem>/<name>@<version>."""
    if purl:
        # Lowercase the type and name portions
        parts = purl.split("/", 1)
        if len(parts) == 2:
            return parts[0].lower() + "/" + parts[1].lower()
        return purl.lower()
    # Fallback: construct from package name
    return f"pkg:pypi/{package_name.lower().replace('-', '_')}"


def _canonical_advisory_id(vuln_id: str) -> str:
    """Normalize advisory ID (uppercase, strip whitespace)."""
    return vuln_id.strip().upper()


def _detect_ecosystem(purl: str) -> str:
    """Detect ecosystem from purl string."""
    purl_lower = purl.lower()
    if "pkg:pypi/" in purl_lower:
        return _ECOSYSTEM_PYPI
    if any(t in purl_lower for t in ("pkg:deb/", "pkg:rpm/", "pkg:apk/", "pkg:alpm/")):
        return _ECOSYSTEM_OS
    # Default: try to infer from type
    if "pkg:" in purl_lower:
        pkg_type = purl_lower.split("pkg:")[1].split("/")[0]
        if pkg_type in ("pypi", "pip"):
            return _ECOSYSTEM_PYPI
        if pkg_type in ("deb", "rpm", "apk", "alpm"):
            return _ECOSYSTEM_OS
    return _ECOSYSTEM_PYPI  # default for this fixture


def _normalize_findings(raw_findings: list[dict], scanner: str) -> list[dict]:
    """Normalize raw findings to canonical keys.

    Canonical finding: (canonical_advisory_id, ecosystem, canonical_purl, installed_version)
    """
    normalized = []
    for f in raw_findings:
        purl = f.get("purl", "")
        pkg = f.get("package_name", "")
        canon_purl = _canonical_purl(purl, pkg)
        ecosystem = _detect_ecosystem(purl or f"pkg:pypi/{pkg}")

        normalized.append({
            "canonical_advisory_id": _canonical_advisory_id(f["vulnerability_id"]),
            "ecosystem": ecosystem,
            "canonical_purl": canon_purl,
            "installed_version": f.get("installed_version", ""),
            "severity": f.get("severity", "UNKNOWN"),
            "fix_version": f.get("fix_version", ""),
            "scanner": scanner,
            "original_vuln_id": f["vulnerability_id"],
            "original_purl": purl,
            "package_name": pkg,
            "data_source": f.get("data_source", ""),
            "related_ids": f.get("related_ids", []),
        })
    return normalized


def _finding_key(f: dict) -> tuple:
    """Compute the canonical deduplication key for a finding."""
    return (
        f["canonical_advisory_id"],
        f["ecosystem"],
        f["canonical_purl"],
        f["installed_version"],
    )


def _deduplicate_findings(findings: list[dict]) -> list[dict]:
    """Deduplicate within a single scanner: same CVE + same package = 1 finding."""
    seen: dict[tuple, dict] = {}
    for f in findings:
        key = _finding_key(f)
        if key not in seen:
            seen[key] = f
        else:
            # Keep the one with more info (prefer higher severity, non-empty fix)
            existing = seen[key]
            if not existing.get("fix_version") and f.get("fix_version"):
                seen[key] = f
    return list(seen.values())


# ===========================================================================
# Stratified Jaccard
# ===========================================================================


def _compute_jaccard(set_a: set, set_b: set) -> dict:
    """Compute Jaccard index and related metrics between two sets."""
    intersection = set_a & set_b
    union = set_a | set_b
    jaccard = round(len(intersection) / len(union), 4) if union else 1.0
    return {
        "scanner_a_total": len(set_a),
        "scanner_b_total": len(set_b),
        "intersection": len(intersection),
        "union": len(union),
        "jaccard": jaccard,
        "a_only": len(set_a - set_b),
        "b_only": len(set_b - set_a),
    }


def _compute_stratified_jaccard(trivy: list[dict], grype: list[dict]) -> dict:
    """Compute stratified Jaccard for multiple strata."""
    trivy_keys_all = {_finding_key(f) for f in trivy}
    grype_keys_all = {_finding_key(f) for f in grype}

    # Stratum: all findings
    all_agreement = _compute_jaccard(trivy_keys_all, grype_keys_all)

    # Stratum: findings with CVE only (canonical_advisory_id starts with CVE-)
    trivy_keys_cve = {k for k in trivy_keys_all if k[0].startswith("CVE-")}
    grype_keys_cve = {k for k in grype_keys_all if k[0].startswith("CVE-")}
    cve_agreement = _compute_jaccard(trivy_keys_cve, grype_keys_cve)

    # Stratum: Python-ecosystem only
    trivy_keys_pypi = {k for k in trivy_keys_all if k[1] == _ECOSYSTEM_PYPI}
    grype_keys_pypi = {k for k in grype_keys_all if k[1] == _ECOSYSTEM_PYPI}
    pypi_agreement = _compute_jaccard(trivy_keys_pypi, grype_keys_pypi)

    return {
        "all": all_agreement,
        "cve_only": cve_agreement,
        "python_ecosystem": pypi_agreement,
    }



# ===========================================================================
# Disagreement taxonomy
# ===========================================================================


def _classify_disagreement(finding: dict, other_scanner_findings: list[dict],
                           other_raw: list[dict]) -> str:
    """Classify an exclusive finding into a disagreement category.

    Categories:
    - advisory_alias_mismatch: same vulnerability, different advisory IDs (e.g. CVE vs GHSA)
    - package_identity_mismatch: same CVE but different package name normalization
    - version_range_interpretation: same CVE+pkg but disagreement on affected versions
    - database_coverage_difference: advisory simply absent from other scanner's DB
    - severity_disagreement: both have it but severity differs enough to filter
    - fix_version_disagreement: both have it but fix versions differ
    - duplicate_record: finding is a duplicate that was not deduplicated in source
    - unknown: cannot classify
    """
    advisory = finding["canonical_advisory_id"]
    pkg_name = finding["package_name"].lower().replace("-", "_")
    canon_purl = finding["canonical_purl"]

    # Build lookup indices from the other scanner
    other_by_advisory: dict[str, list[dict]] = {}
    for of in other_scanner_findings:
        other_by_advisory.setdefault(of["canonical_advisory_id"], []).append(of)

    other_by_pkg: dict[str, list[dict]] = {}
    for of in other_scanner_findings:
        other_by_pkg.setdefault(of["package_name"].lower().replace("-", "_"), []).append(of)

    # Check related IDs (alias check)
    related = [_canonical_advisory_id(r) for r in finding.get("related_ids", []) if r]
    for rel_id in related:
        if rel_id in other_by_advisory:
            # The other scanner has this under a different advisory ID
            other_match = other_by_advisory[rel_id]
            for om in other_match:
                if om["package_name"].lower().replace("-", "_") == pkg_name:
                    return "advisory_alias_mismatch"

    # Check if other scanner has same advisory but different package
    if advisory in other_by_advisory:
        other_same_adv = other_by_advisory[advisory]
        other_pkgs = {of["package_name"].lower().replace("-", "_") for of in other_same_adv}
        if pkg_name not in other_pkgs:
            return "package_identity_mismatch"
        # Same advisory, same package exists in other - version interpretation
        for of in other_same_adv:
            if of["package_name"].lower().replace("-", "_") == pkg_name:
                if of["installed_version"] != finding["installed_version"]:
                    return "version_range_interpretation"
                # Same version but was in other scanner - shouldn't be exclusive
                # Possibly severity filter
                if of.get("severity") != finding.get("severity"):
                    return "severity_disagreement"
                if of.get("fix_version") != finding.get("fix_version"):
                    return "fix_version_disagreement"

    # Check if same package exists in other scanner with any advisory
    if pkg_name in other_by_pkg:
        other_pkg_findings = other_by_pkg[pkg_name]
        other_advisories = {of["canonical_advisory_id"] for of in other_pkg_findings}
        # Check if any related ID matches
        for rel_id in related:
            if rel_id in other_advisories:
                return "advisory_alias_mismatch"
        # Package known but this specific advisory missing
        return "database_coverage_difference"

    # Advisory not found at all in other scanner
    if advisory not in other_by_advisory:
        return "database_coverage_difference"

    return "unknown"


def _build_disagreement_taxonomy(trivy: list[dict], grype: list[dict],
                                 trivy_raw: list[dict], grype_raw: list[dict]) -> list[dict]:
    """Build a taxonomy classifying each exclusive (disagreed) finding."""
    trivy_keys = {_finding_key(f) for f in trivy}
    grype_keys = {_finding_key(f) for f in grype}

    trivy_only_keys = trivy_keys - grype_keys
    grype_only_keys = grype_keys - trivy_keys

    taxonomy_entries = []

    # Classify Trivy-exclusive findings
    trivy_only = [f for f in trivy if _finding_key(f) in trivy_only_keys]
    for f in trivy_only:
        category = _classify_disagreement(f, grype, grype_raw)
        taxonomy_entries.append({
            "canonical_advisory_id": f["canonical_advisory_id"],
            "canonical_purl": f["canonical_purl"],
            "installed_version": f["installed_version"],
            "ecosystem": f["ecosystem"],
            "exclusive_to": "trivy",
            "disagreement_category": category,
            "severity": f.get("severity", ""),
            "fix_version": f.get("fix_version", ""),
            "data_source": f.get("data_source", ""),
        })

    # Classify Grype-exclusive findings
    grype_only = [f for f in grype if _finding_key(f) in grype_only_keys]
    for f in grype_only:
        category = _classify_disagreement(f, trivy, trivy_raw)
        taxonomy_entries.append({
            "canonical_advisory_id": f["canonical_advisory_id"],
            "canonical_purl": f["canonical_purl"],
            "installed_version": f["installed_version"],
            "ecosystem": f["ecosystem"],
            "exclusive_to": "grype",
            "disagreement_category": category,
            "severity": f.get("severity", ""),
            "fix_version": f.get("fix_version", ""),
            "data_source": f.get("data_source", ""),
        })

    return taxonomy_entries


# ===========================================================================
# Scanner DB metadata
# ===========================================================================


def _build_db_metadata(trivy_meta: dict, grype_meta: dict, target_hash: str) -> dict:
    """Assemble scanner DB metadata record."""
    return {
        "target_sbom_hash": target_hash,
        "scanners": {
            "trivy": {
                "available": trivy_meta.get("available", False),
                "scanner_version": trivy_meta.get("scanner_version", "unknown"),
                "db_version": trivy_meta.get("db_version", "unknown"),
                "db_updated_at": trivy_meta.get("db_updated_at", "unknown"),
                "scan_timestamp": trivy_meta.get("scan_timestamp", ""),
            },
            "grype": {
                "available": grype_meta.get("available", False),
                "scanner_version": grype_meta.get("scanner_version", "unknown"),
                "db_version": grype_meta.get("db_version", "unknown"),
                "db_updated_at": grype_meta.get("db_updated_at", "unknown"),
                "scan_timestamp": grype_meta.get("scan_timestamp", ""),
            },
        },
        "metadata_timestamp": datetime.now(timezone.utc).isoformat(),
    }



# ===========================================================================
# VEX policy conformance scenarios (V0-V7)
# ===========================================================================


def _run_vex_scenarios(findings: list[dict], root: Path, result_dir: Path) -> list[dict]:
    """Run VEX policy conformance tests V0-V7."""
    policy = PolicyEngine()
    results = []

    # Pick a finding to use as target (first available, or synthetic)
    if findings:
        target_vuln = findings[0]["canonical_advisory_id"]
        target_component = findings[0]["package_name"]
    else:
        target_vuln = "CVE-2023-FIXTURE"
        target_component = "pillow"

    target_bom_ref = f"comp-{target_component}"

    scenarios = [
        ("V0", "no_vex_baseline", None, GateDecision.VEX_MALFORMED),
        ("V1", "valid_not_affected", _make_vex_not_affected(target_vuln, target_bom_ref), GateDecision.APPROVED),
        ("V2", "wrong_component_linkage", _make_vex_wrong_component(target_vuln), GateDecision.VEX_WRONG_COMPONENT),
        ("V3", "unsigned_local_profile", _make_vex_unsigned(target_vuln, target_bom_ref), GateDecision.APPROVED),
        ("V4", "expired_vex_document", _make_vex_expired(target_vuln, target_bom_ref), GateDecision.VEX_EXPIRED),
        ("V5", "under_investigation", _make_vex_under_investigation(target_vuln, target_bom_ref), GateDecision.APPROVED),
        ("V6", "affected_with_workaround", _make_vex_affected(target_vuln, target_bom_ref), GateDecision.APPROVED),
        ("V7", "fixed_version_inconsistent", _make_vex_fixed_inconsistent(target_vuln, target_bom_ref), GateDecision.APPROVED),
    ]

    for scenario_id, name, vex_doc, expected_decision in scenarios:
        start = time.time()
        result = _evaluate_vex_conformance(
            scenario_id, name, vex_doc, target_vuln, target_bom_ref, policy, expected_decision
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


def _evaluate_vex_conformance(scenario_id: str, name: str, vex_doc: Optional[dict],
                              target_vuln: str, target_bom_ref: str,
                              policy: PolicyEngine, expected: GateDecision) -> dict:
    """Evaluate a single VEX policy conformance test."""
    result = {
        "scenario_id": scenario_id,
        "scenario_name": name,
        "vulnerability_id": target_vuln,
        "target_component": target_bom_ref,
        "vex_status": "N/A",
        "component_linkage": "N/A",
        "signature_state": "N/A",
        "expiration_state": "N/A",
        "expected_decision": expected.value,
        "actual_decision": "",
        "conformance_passed": False,
        "reason_code": "",
    }

    if vex_doc is None:
        # V0: no VEX document provided
        evaluation = policy.evaluate_vex(vex_document=None)
        result["vex_status"] = "no_vex"
        result["actual_decision"] = evaluation.decision.value
        result["reason_code"] = evaluation.reason
        result["conformance_passed"] = (evaluation.decision == expected)
        return result

    # Extract VEX analysis info
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
    result["signature_state"] = "unsigned"

    # Check expiry
    is_expired = False
    metadata = vex_doc.get("metadata", {})
    for prop in metadata.get("properties", []):
        if prop.get("name") == "traceai:expires":
            try:
                exp = datetime.fromisoformat(prop["value"])
                if datetime.now(timezone.utc) > exp:
                    is_expired = True
            except (ValueError, KeyError):
                pass
    result["expiration_state"] = "expired" if is_expired else "valid"

    is_valid_schema = vex_doc.get("bomFormat") == "CycloneDX"

    evaluation = policy.evaluate_vex(
        vex_document=vex_doc,
        vex_signed=False,
        vex_expired=is_expired,
        vex_component_match=component_match,
        vex_schema_valid=is_valid_schema,
    )

    result["actual_decision"] = evaluation.decision.value
    result["reason_code"] = evaluation.reason
    result["conformance_passed"] = (evaluation.decision == expected)

    return result


# VEX document generators

def _make_vex_not_affected(vuln_id: str, bom_ref: str) -> dict:
    """V1: Valid not_affected VEX."""
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "vulnerabilities": [{
            "id": vuln_id,
            "analysis": {"state": "not_affected", "justification": "code_not_reachable",
                         "detail": "Controlled test fixture - code path not exercised"},
            "affects": [{"ref": bom_ref}],
        }],
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "properties": []},
    }


def _make_vex_wrong_component(vuln_id: str) -> dict:
    """V2: VEX linked to wrong component."""
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "vulnerabilities": [{
            "id": vuln_id,
            "analysis": {"state": "not_affected", "justification": "code_not_reachable"},
            "affects": [{"ref": "comp-WRONG-COMPONENT"}],
        }],
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "properties": []},
    }


def _make_vex_unsigned(vuln_id: str, bom_ref: str) -> dict:
    """V3: Unsigned VEX (allowed in local profile)."""
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "vulnerabilities": [{
            "id": vuln_id,
            "analysis": {"state": "not_affected", "justification": "code_not_reachable"},
            "affects": [{"ref": bom_ref}],
        }],
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "properties": []},
    }


def _make_vex_expired(vuln_id: str, bom_ref: str) -> dict:
    """V4: Expired VEX document."""
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


def _make_vex_under_investigation(vuln_id: str, bom_ref: str) -> dict:
    """V5: Under investigation status."""
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "vulnerabilities": [{
            "id": vuln_id,
            "analysis": {"state": "under_investigation"},
            "affects": [{"ref": bom_ref}],
        }],
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "properties": []},
    }


def _make_vex_affected(vuln_id: str, bom_ref: str) -> dict:
    """V6: Affected with workaround available."""
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "vulnerabilities": [{
            "id": vuln_id,
            "analysis": {"state": "affected", "response": ["workaround_available"]},
            "affects": [{"ref": bom_ref}],
        }],
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "properties": []},
    }


def _make_vex_fixed_inconsistent(vuln_id: str, bom_ref: str) -> dict:
    """V7: Fixed but installed version is still vulnerable."""
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "vulnerabilities": [{
            "id": vuln_id,
            "analysis": {"state": "fixed", "detail": "Fixed in 10.0.0 but 9.0.0 installed"},
            "affects": [{"ref": bom_ref}],
        }],
        "metadata": {"timestamp": datetime.now(timezone.utc).isoformat(), "properties": []},
    }



# ===========================================================================
# Output generation
# ===========================================================================


def _save_results_dir(trivy: list[dict], grype: list[dict], agreement: dict,
                      vex_results: list[dict], result_dir: Path,
                      campaign_id: str, profile: str, quick: bool) -> None:
    """Save outputs to the results directory."""
    # scanner_findings_normalized.csv
    all_findings = trivy + grype
    if all_findings:
        csv_path = result_dir / "scanner_findings_normalized.csv"
        fieldnames = [
            "canonical_advisory_id", "ecosystem", "canonical_purl", "installed_version",
            "severity", "fix_version", "scanner", "package_name", "data_source",
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_findings)

    # scanner_agreement.csv
    agree_path = result_dir / "scanner_agreement.csv"
    with open(agree_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["stratum", "metric", "value"])
        for stratum_name, metrics in agreement.items():
            for metric_name, value in metrics.items():
                writer.writerow([stratum_name, metric_name, value])

    # rq3_summary.json
    conformance_passed = sum(1 for v in vex_results if v["conformance_passed"])
    summary = {
        "campaign_id": campaign_id,
        "profile": profile,
        "quick": quick,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scanner_agreement": agreement,
        "vex_scenario_count": len(vex_results),
        "vex_conformance_passed": conformance_passed,
        "vex_conformance_total": len(vex_results),
        "vex_conformance_summary": f"policy conformance: {conformance_passed}/{len(vex_results)} rules passed",
    }
    with open(result_dir / "rq3_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def _save_generated_dir(agreement: dict, taxonomy: list[dict],
                        db_metadata: dict, vex_results: list[dict],
                        gen_dir: Path) -> None:
    """Save generated outputs (LaTeX, CSV, JSON) to generated/rq3/."""
    from traceai.environment import escape_latex

    # database_metadata.json
    with open(gen_dir / "database_metadata.json", "w", encoding="utf-8") as f:
        json.dump(db_metadata, f, indent=2)

    # disagreement_details.csv
    if taxonomy:
        csv_path = gen_dir / "disagreement_details.csv"
        fieldnames = list(taxonomy[0].keys())
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(taxonomy)
    else:
        # Write empty file with headers
        csv_path = gen_dir / "disagreement_details.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "canonical_advisory_id", "canonical_purl", "installed_version",
                "ecosystem", "exclusive_to", "disagreement_category",
                "severity", "fix_version", "data_source",
            ])

    # scanner_agreement_stratified.tex
    _generate_agreement_table(agreement, gen_dir, escape_latex)

    # disagreement_taxonomy.tex
    _generate_taxonomy_table(taxonomy, gen_dir, escape_latex)

    # vex_conformance_table.tex
    _generate_vex_conformance_table(vex_results, gen_dir, escape_latex)


def _generate_agreement_table(agreement: dict, gen_dir: Path, escape_latex) -> None:
    """Generate scanner_agreement_stratified.tex."""
    lines = [
        r"\begin{table}[htbp]",
        r"\caption{Stratified Scanner Finding Overlap (RQ3)}",
        r"\label{tab:scanner-agreement-stratified}",
        r"\centering\small",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        r"\textbf{Stratum} & \textbf{Trivy} & \textbf{Grype} & \textbf{Intersection} & \textbf{Jaccard} \\",
        r"\midrule",
    ]

    stratum_labels = {
        "all": "All findings",
        "cve_only": "CVE-identified only",
        "python_ecosystem": "Python packages only",
    }

    for key, label in stratum_labels.items():
        metrics = agreement.get(key, {})
        trivy_n = metrics.get("scanner_a_total", 0)
        grype_n = metrics.get("scanner_b_total", 0)
        inter = metrics.get("intersection", 0)
        jaccard = metrics.get("jaccard", 0.0)
        lines.append(
            f"  {escape_latex(label)} & {trivy_n} & {grype_n} & {inter} & {jaccard:.4f} \\\\"
        )

    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    (gen_dir / "scanner_agreement_stratified.tex").write_text("\n".join(lines), encoding="utf-8")


def _generate_taxonomy_table(taxonomy: list[dict], gen_dir: Path, escape_latex) -> None:
    """Generate disagreement_taxonomy.tex."""
    # Aggregate counts by category
    category_counts: dict[str, dict[str, int]] = {}
    for entry in taxonomy:
        cat = entry["disagreement_category"]
        scanner = entry["exclusive_to"]
        if cat not in category_counts:
            category_counts[cat] = {"trivy": 0, "grype": 0, "total": 0}
        category_counts[cat][scanner] += 1
        category_counts[cat]["total"] += 1

    lines = [
        r"\begin{table}[htbp]",
        r"\caption{Disagreement Taxonomy (RQ3)}",
        r"\label{tab:disagreement-taxonomy}",
        r"\centering\small",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"\textbf{Category} & \textbf{Trivy-only} & \textbf{Grype-only} & \textbf{Total} \\",
        r"\midrule",
    ]

    for cat in _DISAGREEMENT_CATEGORIES:
        counts = category_counts.get(cat, {"trivy": 0, "grype": 0, "total": 0})
        if counts["total"] > 0:
            label = cat.replace("_", " ").title()
            lines.append(
                f"  {escape_latex(label)} & {counts['trivy']} & {counts['grype']} & {counts['total']} \\\\"
            )

    # Total row
    total_trivy = sum(c.get("trivy", 0) for c in category_counts.values())
    total_grype = sum(c.get("grype", 0) for c in category_counts.values())
    total_all = total_trivy + total_grype
    lines.append(r"\midrule")
    lines.append(f"  \\textbf{{Total}} & {total_trivy} & {total_grype} & {total_all} \\\\")

    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    (gen_dir / "disagreement_taxonomy.tex").write_text("\n".join(lines), encoding="utf-8")


def _generate_vex_conformance_table(vex_results: list[dict], gen_dir: Path, escape_latex) -> None:
    """Generate vex_conformance_table.tex."""
    conformance_passed = sum(1 for v in vex_results if v["conformance_passed"])

    lines = [
        r"\begin{table}[htbp]",
        r"\caption{VEX Policy Conformance Tests (RQ3)}",
        r"\label{tab:vex-conformance}",
        r"\centering\small",
        r"\begin{tabular}{llllc}",
        r"\toprule",
        r"\textbf{ID} & \textbf{Scenario} & \textbf{Expected} & \textbf{Actual} & \textbf{Pass} \\",
        r"\midrule",
    ]

    for v in vex_results:
        passed = r"\checkmark" if v["conformance_passed"] else r"$\times$"
        lines.append(
            f"  {v['scenario_id']} & {escape_latex(v['scenario_name'])} & "
            f"{escape_latex(v['expected_decision'])} & "
            f"{escape_latex(v['actual_decision'])} & {passed} \\\\"
        )

    lines.append(r"\midrule")
    lines.append(
        f"  \\multicolumn{{4}}{{l}}{{\\textbf{{Policy conformance: "
        f"{conformance_passed}/{len(vex_results)} rules passed}}}} & \\\\"
    )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    (gen_dir / "vex_conformance_table.tex").write_text("\n".join(lines), encoding="utf-8")
