"""Phase 3: RQ3 Agreement Views — Scanner overlap analysis.

Uses ONLY existing raw Trivy and Grype JSON outputs.
Does NOT query OSV or external APIs.
Does NOT infer CVE/GHSA equivalence from package name + version alone.
Extracts aliases ONLY when explicitly present in scanner output.
"""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "results" / "rq3" / "rq3-20260722-140819-082e9531" / "raw"
OUT_DIR = ROOT / "generated" / "rq3" / "phase3_agreement"
OUT_DIR.mkdir(parents=True, exist_ok=True)

REQUIREMENTS = ROOT / "requirements-exact.txt"


def load_direct_deps() -> set[str]:
    """Load direct dependency names from requirements-exact.txt."""
    if not REQUIREMENTS.exists():
        return set()
    deps = set()
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip()
        deps.add(name.lower())
    return deps


def main() -> int:
    ts_start = datetime.now(timezone.utc)
    print(f"[Phase 3] Start: {ts_start.isoformat()}")

    # Load scanner outputs
    trivy_data = json.loads(
        (RAW_DIR / "trivy_scan_results.json").read_text(encoding="utf-8")
    )
    grype_data = json.loads(
        (RAW_DIR / "grype_scan_results.json").read_text(encoding="utf-8")
    )
    direct_deps = load_direct_deps()

    # --- Stage 1: Extract normalized findings ---
    print("[Phase 3] Stage 1: Extracting normalized findings...")
    trivy_findings = extract_trivy_findings(trivy_data)
    grype_findings = extract_grype_findings(grype_data)
    save_stage("stage1_trivy_findings.json", trivy_findings)
    save_stage("stage1_grype_findings.json", grype_findings)
    print(f"  Trivy findings: {len(trivy_findings)}")
    print(f"  Grype findings: {len(grype_findings)}")

    # --- Stage 2: Raw primary-identifier overlap ---
    print("[Phase 3] Stage 2: Raw primary-identifier overlap...")
    trivy_ids = set(f["primary_id"] for f in trivy_findings)
    grype_ids = set(f["primary_id"] for f in grype_findings)
    raw_overlap = compute_overlap(trivy_ids, grype_ids, "raw_primary_id")
    save_stage("stage2_raw_id_overlap.json", raw_overlap)
    print(f"  Overlap: {raw_overlap['intersection_size']}, "
          f"Jaccard: {raw_overlap['jaccard']:.4f}")

    # --- Stage 3: Alias-expanded overlap ---
    print("[Phase 3] Stage 3: Alias-expanded overlap...")
    alias_map = build_alias_map_from_scanner_output(grype_data, trivy_data)
    alias_result = compute_alias_expanded_overlap(
        trivy_ids, grype_ids, alias_map
    )
    save_stage("stage3_alias_expanded_overlap.json", alias_result)
    if alias_result["computable"]:
        print(f"  Expanded overlap: {alias_result['intersection_size']}, "
              f"Jaccard: {alias_result['jaccard']:.4f}")
    else:
        print(f"  Result: NOT_COMPUTABLE — {alias_result['reason']}")

    # --- Stage 4: Affected package-PURL overlap ---
    print("[Phase 3] Stage 4: Affected package-PURL overlap...")
    trivy_purls = set(f["purl"] for f in trivy_findings if f["purl"])
    grype_purls = set(f["purl"] for f in grype_findings if f["purl"])
    purl_overlap = compute_overlap(trivy_purls, grype_purls, "affected_purl")
    save_stage("stage4_purl_overlap.json", purl_overlap)
    print(f"  Trivy PURLs: {len(trivy_purls)}, Grype PURLs: {len(grype_purls)}, "
          f"Overlap: {purl_overlap['intersection_size']}")

    # --- Stage 5: Affected package-version overlap ---
    print("[Phase 3] Stage 5: Affected package-version overlap...")
    trivy_pkgver = set((f["pkg_name"], f["version"]) for f in trivy_findings)
    grype_pkgver = set((f["pkg_name"], f["version"]) for f in grype_findings)
    pkgver_overlap = compute_overlap(trivy_pkgver, grype_pkgver, "pkg_version")
    save_stage("stage5_pkgver_overlap.json", pkgver_overlap)
    print(f"  Trivy (pkg,ver): {len(trivy_pkgver)}, Grype: {len(grype_pkgver)}, "
          f"Overlap: {pkgver_overlap['intersection_size']}")

    # --- Stage 6: Direct vs transitive dependency overlap ---
    print("[Phase 3] Stage 6: Direct/transitive dependency classification...")
    dep_analysis = classify_dependency_overlap(
        trivy_findings, grype_findings, direct_deps
    )
    save_stage("stage6_dependency_overlap.json", dep_analysis)
    print(f"  Direct dep findings (Trivy): {dep_analysis['trivy_direct']}, "
          f"Transitive: {dep_analysis['trivy_transitive']}")
    print(f"  Direct dep findings (Grype): {dep_analysis['grype_direct']}, "
          f"Transitive: {dep_analysis['grype_transitive']}")

    # --- Stage 7: Unresolved alias list ---
    print("[Phase 3] Stage 7: Generating unresolved-alias list...")
    unresolved = generate_unresolved_alias_list(
        trivy_ids, grype_ids, alias_map
    )
    save_stage("stage7_unresolved_aliases.json", unresolved)
    save_csv("stage7_unresolved_aliases.csv", unresolved["entries"])
    print(f"  Unresolved IDs: {len(unresolved['entries'])}")

    # --- Stage 8: Scanner-exclusive classification ---
    print("[Phase 3] Stage 8: Classifying scanner-exclusive findings...")
    exclusives = classify_scanner_exclusives(
        trivy_findings, grype_findings, alias_map, direct_deps
    )
    save_stage("stage8_scanner_exclusives.json", exclusives)
    save_csv("stage8_trivy_exclusive.csv", exclusives["trivy_exclusive"])
    save_csv("stage8_grype_exclusive.csv", exclusives["grype_exclusive"])
    print(f"  Trivy-exclusive: {len(exclusives['trivy_exclusive'])}")
    print(f"  Grype-exclusive: {len(exclusives['grype_exclusive'])}")

    # --- Final summary ---
    ts_end = datetime.now(timezone.utc)
    summary = build_summary(
        trivy_findings, grype_findings, raw_overlap, alias_result,
        purl_overlap, pkgver_overlap, dep_analysis, unresolved,
        exclusives, ts_start, ts_end
    )
    save_stage("rq3_agreement_summary.json", summary)
    generate_latex_table(summary)

    print(f"\n[Phase 3] Complete. Duration: {(ts_end - ts_start).total_seconds():.1f}s")
    print(f"[Phase 3] Outputs: {OUT_DIR}")
    return 0


# ===========================================================================
# Extraction
# ===========================================================================

def extract_trivy_findings(data: dict) -> list[dict]:
    """Extract normalized findings from Trivy JSON output."""
    findings = []
    for result in data.get("Results", []):
        for v in (result.get("Vulnerabilities") or []):
            pkg = v.get("PkgName", "")
            version = v.get("InstalledVersion", "")
            purl = f"pkg:pypi/{pkg.lower()}@{version}" if pkg else ""
            findings.append({
                "primary_id": v.get("VulnerabilityID", ""),
                "pkg_name": pkg.lower(),
                "version": version,
                "purl": purl,
                "severity": v.get("Severity", "UNKNOWN").upper(),
                "fixed_version": v.get("FixedVersion", ""),
                "scanner": "trivy",
                "data_source": v.get("DataSource", {}).get("ID", ""),
            })
    return findings


def extract_grype_findings(data: dict) -> list[dict]:
    """Extract normalized findings from Grype JSON output."""
    findings = []
    for m in data.get("matches", []):
        vuln = m.get("vulnerability", {})
        artifact = m.get("artifact", {})
        pkg = artifact.get("name", "")
        version = artifact.get("version", "")
        purl = artifact.get("purl", "")
        if not purl and pkg:
            purl = f"pkg:pypi/{pkg.lower()}@{version}"
        fix = vuln.get("fix", {})
        fix_versions = fix.get("versions", []) if isinstance(fix, dict) else []
        findings.append({
            "primary_id": vuln.get("id", ""),
            "pkg_name": pkg.lower(),
            "version": version,
            "purl": purl,
            "severity": vuln.get("severity", "Unknown").upper(),
            "fixed_version": ", ".join(fix_versions) if fix_versions else "",
            "scanner": "grype",
            "data_source": vuln.get("dataSource", ""),
        })
    return findings


# ===========================================================================
# Alias map construction (from scanner output ONLY)
# ===========================================================================

def build_alias_map_from_scanner_output(
    grype_data: dict, trivy_data: dict
) -> dict[str, set[str]]:
    """Build bidirectional alias map using ONLY explicit data in scanner outputs.

    Sources:
    - Grype: relatedVulnerabilities[].id provides CVE for each GHSA
    - Trivy: VendorIDs field (if present) lists GHSA equivalents
    """
    alias_map: dict[str, set[str]] = {}

    # From Grype: GHSA primary -> CVE in relatedVulnerabilities
    for m in grype_data.get("matches", []):
        primary = m.get("vulnerability", {}).get("id", "")
        for rv in m.get("relatedVulnerabilities", []):
            rv_id = rv.get("id", "")
            if primary and rv_id and primary != rv_id:
                alias_map.setdefault(primary, set()).add(rv_id)
                alias_map.setdefault(rv_id, set()).add(primary)

    # From Trivy: VendorIDs field
    for result in trivy_data.get("Results", []):
        for v in (result.get("Vulnerabilities") or []):
            primary = v.get("VulnerabilityID", "")
            vendor_ids = v.get("VendorIDs") or []
            for vid in vendor_ids:
                if primary and vid and primary != vid:
                    alias_map.setdefault(primary, set()).add(vid)
                    alias_map.setdefault(vid, set()).add(primary)

    return alias_map


# ===========================================================================
# Overlap computation
# ===========================================================================

def compute_overlap(set_a: set, set_b: set, label: str) -> dict:
    """Compute basic set overlap metrics."""
    intersection = set_a & set_b
    union = set_a | set_b
    jaccard = len(intersection) / len(union) if union else 0.0
    return {
        "label": label,
        "set_a_size": len(set_a),
        "set_b_size": len(set_b),
        "intersection_size": len(intersection),
        "union_size": len(union),
        "jaccard": round(jaccard, 4),
        "a_only_size": len(set_a - set_b),
        "b_only_size": len(set_b - set_a),
    }


def compute_alias_expanded_overlap(
    trivy_ids: set[str], grype_ids: set[str], alias_map: dict[str, set[str]]
) -> dict:
    """Compute overlap after expanding IDs via alias map.

    Only uses aliases explicitly present in scanner output.
    Returns NOT_COMPUTABLE if no alias evidence is available.
    """
    if not alias_map:
        return {
            "computable": False,
            "result": "NOT_COMPUTABLE",
            "reason": "No alias mappings found in scanner output",
            "intersection_size": 0,
            "jaccard": 0.0,
        }

    # Expand both sets
    trivy_expanded = set()
    for vid in trivy_ids:
        trivy_expanded.add(vid)
        trivy_expanded.update(alias_map.get(vid, set()))

    grype_expanded = set()
    for vid in grype_ids:
        grype_expanded.add(vid)
        grype_expanded.update(alias_map.get(vid, set()))

    intersection = trivy_expanded & grype_expanded
    union = trivy_expanded | grype_expanded
    jaccard = len(intersection) / len(union) if union else 0.0

    return {
        "computable": True,
        "result": "COMPUTED",
        "alias_sources": [
            "grype.relatedVulnerabilities[].id",
            "trivy.VendorIDs",
        ],
        "alias_mappings_count": sum(len(v) for v in alias_map.values()) // 2,
        "trivy_expanded_size": len(trivy_expanded),
        "grype_expanded_size": len(grype_expanded),
        "intersection_size": len(intersection),
        "union_size": len(union),
        "jaccard": round(jaccard, 4),
    }


def classify_dependency_overlap(
    trivy_findings: list[dict],
    grype_findings: list[dict],
    direct_deps: set[str],
) -> dict:
    """Classify findings by direct vs transitive dependency."""
    def classify(findings):
        direct = [f for f in findings if f["pkg_name"] in direct_deps]
        transitive = [f for f in findings if f["pkg_name"] not in direct_deps]
        return direct, transitive

    trivy_d, trivy_t = classify(trivy_findings)
    grype_d, grype_t = classify(grype_findings)

    # Overlap on direct deps
    trivy_direct_ids = set(f["primary_id"] for f in trivy_d)
    grype_direct_ids = set(f["primary_id"] for f in grype_d)
    trivy_trans_ids = set(f["primary_id"] for f in trivy_t)
    grype_trans_ids = set(f["primary_id"] for f in grype_t)

    return {
        "trivy_direct": len(trivy_d),
        "trivy_transitive": len(trivy_t),
        "grype_direct": len(grype_d),
        "grype_transitive": len(grype_t),
        "direct_id_overlap": len(trivy_direct_ids & grype_direct_ids),
        "transitive_id_overlap": len(trivy_trans_ids & grype_trans_ids),
        "direct_deps_scanned": sorted(
            set(f["pkg_name"] for f in trivy_d + grype_d)
        ),
    }


# ===========================================================================
# Unresolved aliases
# ===========================================================================

def generate_unresolved_alias_list(
    trivy_ids: set[str], grype_ids: set[str], alias_map: dict[str, set[str]]
) -> dict:
    """Generate list of IDs that remain unresolved after alias expansion."""
    # Find IDs exclusive to one scanner that have NO alias mapping
    trivy_only = trivy_ids - grype_ids
    grype_only = grype_ids - trivy_ids

    entries = []
    for vid in sorted(trivy_only):
        aliases = alias_map.get(vid, set())
        resolved = bool(aliases & grype_ids)
        if not resolved:
            # Check if any of its aliases appear expanded in grype
            expanded_match = any(
                a in grype_ids or bool(alias_map.get(a, set()) & grype_ids)
                for a in aliases
            )
            entries.append({
                "id": vid,
                "scanner": "trivy",
                "has_alias_in_map": bool(aliases),
                "aliases": sorted(aliases),
                "resolved_via_alias": expanded_match,
            })

    for vid in sorted(grype_only):
        aliases = alias_map.get(vid, set())
        resolved = bool(aliases & trivy_ids)
        if not resolved:
            expanded_match = any(
                a in trivy_ids or bool(alias_map.get(a, set()) & trivy_ids)
                for a in aliases
            )
            entries.append({
                "id": vid,
                "scanner": "grype",
                "has_alias_in_map": bool(aliases),
                "aliases": sorted(aliases),
                "resolved_via_alias": expanded_match,
            })

    return {
        "description": "IDs exclusive to one scanner with no direct or alias match in the other",
        "total_unresolved": len([e for e in entries if not e["resolved_via_alias"]]),
        "total_entries": len(entries),
        "entries": entries,
    }


# ===========================================================================
# Scanner-exclusive classification
# ===========================================================================

# Evidence-supported categories for exclusives
EXCLUSIVE_CATEGORIES = {
    "ADVISORY_ALIAS_RESOLVED": "Finding maps to other scanner via explicit alias in relatedVulnerabilities/VendorIDs",
    "DATABASE_COVERAGE_GAP": "No alias mapping exists; scanner uses a DB the other does not cover",
    "ID_NAMESPACE_DIFFERENCE": "Same vulnerability, different namespace (GHSA vs CVE) confirmed by alias",
    "SEVERITY_THRESHOLD": "Present in both DBs but one scanner filters below threshold",
    "VERSION_RANGE_EXCLUSION": "Scanner's version-range matching excludes this package version",
    "UNCLASSIFIABLE": "Insufficient evidence in scanner output to determine cause",
}


def classify_scanner_exclusives(
    trivy_findings: list[dict],
    grype_findings: list[dict],
    alias_map: dict[str, set[str]],
    direct_deps: set[str],
) -> dict:
    """Classify scanner-exclusive findings using evidence-supported categories."""
    trivy_ids = set(f["primary_id"] for f in trivy_findings)
    grype_ids = set(f["primary_id"] for f in grype_findings)

    # Build pkg->findings maps
    grype_by_pkg = {}
    for f in grype_findings:
        grype_by_pkg.setdefault(f["pkg_name"], []).append(f)
    trivy_by_pkg = {}
    for f in trivy_findings:
        trivy_by_pkg.setdefault(f["pkg_name"], []).append(f)

    trivy_exclusive = []
    for f in trivy_findings:
        vid = f["primary_id"]
        if vid in grype_ids:
            continue  # not exclusive
        aliases = alias_map.get(vid, set())
        if aliases & grype_ids:
            category = "ADVISORY_ALIAS_RESOLVED"
        elif aliases:
            # Has aliases but they're not in grype
            category = "ID_NAMESPACE_DIFFERENCE"
        elif f["pkg_name"] in grype_by_pkg:
            # Same pkg scanned by grype but this CVE not reported
            category = "DATABASE_COVERAGE_GAP"
        else:
            category = "UNCLASSIFIABLE"

        trivy_exclusive.append({
            "id": vid,
            "pkg_name": f["pkg_name"],
            "version": f["version"],
            "severity": f["severity"],
            "category": category,
            "evidence": EXCLUSIVE_CATEGORIES[category],
            "aliases_in_output": sorted(aliases),
            "is_direct_dep": f["pkg_name"] in direct_deps,
        })

    grype_exclusive = []
    for f in grype_findings:
        vid = f["primary_id"]
        if vid in trivy_ids:
            continue
        aliases = alias_map.get(vid, set())
        if aliases & trivy_ids:
            category = "ADVISORY_ALIAS_RESOLVED"
        elif aliases:
            category = "ID_NAMESPACE_DIFFERENCE"
        elif f["pkg_name"] in trivy_by_pkg:
            category = "DATABASE_COVERAGE_GAP"
        else:
            category = "UNCLASSIFIABLE"

        grype_exclusive.append({
            "id": vid,
            "pkg_name": f["pkg_name"],
            "version": f["version"],
            "severity": f["severity"],
            "category": category,
            "evidence": EXCLUSIVE_CATEGORIES[category],
            "aliases_in_output": sorted(aliases),
            "is_direct_dep": f["pkg_name"] in direct_deps,
        })

    # Category summary
    trivy_cats = {}
    for e in trivy_exclusive:
        trivy_cats[e["category"]] = trivy_cats.get(e["category"], 0) + 1
    grype_cats = {}
    for e in grype_exclusive:
        grype_cats[e["category"]] = grype_cats.get(e["category"], 0) + 1

    return {
        "trivy_exclusive": trivy_exclusive,
        "grype_exclusive": grype_exclusive,
        "trivy_category_counts": trivy_cats,
        "grype_category_counts": grype_cats,
        "categories_used": EXCLUSIVE_CATEGORIES,
    }


# ===========================================================================
# Summary & output
# ===========================================================================

def build_summary(
    trivy_findings, grype_findings, raw_overlap, alias_result,
    purl_overlap, pkgver_overlap, dep_analysis, unresolved,
    exclusives, ts_start, ts_end,
) -> dict:
    return {
        "phase": "Phase 3: RQ3 Agreement Views",
        "timestamp_start": ts_start.isoformat(),
        "timestamp_end": ts_end.isoformat(),
        "scanner_raw_dir": str(RAW_DIR),
        "trivy_total_findings": len(trivy_findings),
        "grype_total_findings": len(grype_findings),
        "raw_primary_id_overlap": raw_overlap,
        "alias_expanded_overlap": alias_result,
        "affected_purl_overlap": purl_overlap,
        "affected_pkgver_overlap": pkgver_overlap,
        "dependency_classification": dep_analysis,
        "unresolved_aliases_count": unresolved["total_unresolved"],
        "trivy_exclusive_count": len(exclusives["trivy_exclusive"]),
        "grype_exclusive_count": len(exclusives["grype_exclusive"]),
        "trivy_exclusive_categories": exclusives["trivy_category_counts"],
        "grype_exclusive_categories": exclusives["grype_category_counts"],
    }


def generate_latex_table(summary: dict) -> None:
    """Generate LaTeX table for scanner agreement."""
    raw = summary["raw_primary_id_overlap"]
    alias = summary["alias_expanded_overlap"]
    purl = summary["affected_purl_overlap"]
    pkgver = summary["affected_pkgver_overlap"]

    alias_jaccard = (
        f"{alias['jaccard']:.4f}" if alias.get("computable") else "N/C"
    )

    tex = r"""\begin{table}[htbp]
\caption{RQ3 Scanner Agreement: Multi-View Overlap Analysis}
\label{tab:rq3-agreement}
\centering\small
\begin{tabular}{lrrrr}
\toprule
\textbf{Overlap View} & \textbf{$|A|$} & \textbf{$|B|$} & \textbf{$|A \cap B|$} & \textbf{Jaccard} \\
\midrule
"""
    tex += f"  Raw Primary ID & {raw['set_a_size']} & {raw['set_b_size']} & {raw['intersection_size']} & {raw['jaccard']:.4f} \\\\\n"
    tex += f"  Alias-Expanded & {alias.get('trivy_expanded_size', 'N/A')} & {alias.get('grype_expanded_size', 'N/A')} & {alias.get('intersection_size', 'N/A')} & {alias_jaccard} \\\\\n"
    tex += f"  Affected PURL & {purl['set_a_size']} & {purl['set_b_size']} & {purl['intersection_size']} & {purl['jaccard']:.4f} \\\\\n"
    tex += f"  Affected (pkg, ver) & {pkgver['set_a_size']} & {pkgver['set_b_size']} & {pkgver['intersection_size']} & {pkgver['jaccard']:.4f} \\\\\n"
    tex += r"""\bottomrule
\end{tabular}
\end{table}
"""
    (OUT_DIR / "rq3_agreement_table.tex").write_text(tex, encoding="utf-8")
    print(f"  LaTeX table: {OUT_DIR / 'rq3_agreement_table.tex'}")


# ===========================================================================
# I/O helpers
# ===========================================================================

def save_stage(filename: str, data: Any) -> None:
    """Save intermediate JSON output."""
    path = OUT_DIR / filename
    path.write_text(
        json.dumps(data, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )


def save_csv(filename: str, rows: list[dict]) -> None:
    """Save list of dicts as CSV."""
    if not rows:
        (OUT_DIR / filename).write_text("# empty\n", encoding="utf-8")
        return
    path = OUT_DIR / filename
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            # Convert lists/sets to strings for CSV
            csv_row = {}
            for k, v in row.items():
                if isinstance(v, (list, set)):
                    csv_row[k] = "; ".join(str(x) for x in v)
                else:
                    csv_row[k] = v
            writer.writerow(csv_row)


if __name__ == "__main__":
    sys.exit(main())
