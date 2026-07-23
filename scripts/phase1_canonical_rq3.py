"""Phase 1: Canonicalize RQ3 Advisory Equivalence Classes.

Replaces set-expansion (which incorrectly inflated intersection to 66) with
equivalence-class canonicalization using union-find.

The previous intersection of 66 was invalid because alias expansion added
BOTH the GHSA and CVE identifiers to each scanner's expanded set, then
counted each identifier as a separate match. When a single vulnerability
has both CVE-X and GHSA-Y, and both appear in the expanded sets, that
counts as 2 intersecting elements rather than 1 equivalence class.
The correct approach: map each finding to its canonical equivalence class
and count each class ONCE per (scanner, package, version).
"""
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "results" / "rq3" / "rq3-20260722-140819-082e9531" / "raw"
OUT_DIR = ROOT / "generated" / "rq3"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ===========================================================================
# Union-Find for equivalence classes
# ===========================================================================

class UnionFind:
    """Disjoint-set / union-find data structure."""

    def __init__(self):
        self.parent: dict[str, str] = {}
        self.rank: dict[str, int] = {}

    def find(self, x: str) -> str:
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: str, y: str) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1

    def get_components(self) -> dict[str, set[str]]:
        """Return {root: set of all members} for each component."""
        components: dict[str, set[str]] = defaultdict(set)
        for x in self.parent:
            components[self.find(x)].add(x)
        return dict(components)


def choose_canonical_id(members: set[str]) -> str:
    """Choose canonical ID: prefer CVE, then GHSA, then lexicographic smallest."""
    cves = sorted(m for m in members if m.startswith("CVE-"))
    if cves:
        return cves[0]
    ghsas = sorted(m for m in members if m.startswith("GHSA-"))
    if ghsas:
        return ghsas[0]
    return sorted(members)[0]


# ===========================================================================
# Alias graph construction from scanner output ONLY
# ===========================================================================

def build_alias_graph(trivy_data: dict, grype_data: dict) -> UnionFind:
    """Build alias graph using ONLY explicit relations in scanner output.

    Sources:
    - Grype: match.vulnerability.id <-> match.relatedVulnerabilities[].id
    - Trivy: VulnerabilityID <-> VendorIDs[] (when present)
    """
    uf = UnionFind()

    # Grype: primary GHSA linked to related CVE
    for m in grype_data.get("matches", []):
        primary = m.get("vulnerability", {}).get("id", "")
        if not primary:
            continue
        uf.find(primary)  # ensure it exists
        for rv in m.get("relatedVulnerabilities", []):
            rv_id = rv.get("id", "")
            if rv_id and rv_id != primary:
                uf.union(primary, rv_id)

    # Trivy: VulnerabilityID linked to VendorIDs
    for result in trivy_data.get("Results", []):
        for v in (result.get("Vulnerabilities") or []):
            primary = v.get("VulnerabilityID", "")
            if not primary:
                continue
            uf.find(primary)  # ensure it exists
            for vid in (v.get("VendorIDs") or []):
                if vid and vid != primary:
                    uf.union(primary, vid)

    return uf


# ===========================================================================
# Finding extraction and canonicalization
# ===========================================================================

def extract_and_canonicalize(
    trivy_data: dict, grype_data: dict, uf: UnionFind, canonical_map: dict[str, str]
) -> tuple[list[dict], list[dict]]:
    """Extract findings and map each to its canonical class."""

    trivy_findings = []
    for result in trivy_data.get("Results", []):
        for v in (result.get("Vulnerabilities") or []):
            vid = v.get("VulnerabilityID", "")
            pkg = v.get("PkgName", "").lower()
            version = v.get("InstalledVersion", "")
            purl = f"pkg:pypi/{pkg}@{version}" if pkg else ""
            canonical = canonical_map.get(uf.find(vid), vid)
            trivy_findings.append({
                "primary_id": vid,
                "canonical_class": canonical,
                "pkg_name": pkg,
                "version": version,
                "purl": purl,
                "severity": v.get("Severity", "UNKNOWN").upper(),
                "fixed_version": v.get("FixedVersion", ""),
                "scanner": "trivy",
            })

    grype_findings = []
    for m in grype_data.get("matches", []):
        vuln = m.get("vulnerability", {})
        vid = vuln.get("id", "")
        artifact = m.get("artifact", {})
        pkg = artifact.get("name", "").lower()
        version = artifact.get("version", "")
        purl = artifact.get("purl", "") or (f"pkg:pypi/{pkg}@{version}" if pkg else "")
        fix = vuln.get("fix", {})
        fix_ver = ", ".join(fix.get("versions", [])) if isinstance(fix, dict) else ""
        canonical = canonical_map.get(uf.find(vid), vid)
        grype_findings.append({
            "primary_id": vid,
            "canonical_class": canonical,
            "pkg_name": pkg,
            "version": version,
            "purl": purl,
            "severity": vuln.get("severity", "Unknown").upper(),
            "fixed_version": fix_ver,
            "scanner": "grype",
        })

    return trivy_findings, grype_findings


def deduplicate_canonical(findings: list[dict]) -> list[dict]:
    """Deduplicate: one entry per (canonical_class, pkg_name, version) per scanner."""
    seen = set()
    deduped = []
    for f in findings:
        key = (f["canonical_class"], f["pkg_name"], f["version"])
        if key not in seen:
            seen.add(key)
            deduped.append(f)
    return deduped


# ===========================================================================
# Metric computation
# ===========================================================================

def compute_canonical_metrics(
    trivy_deduped: list[dict], grype_deduped: list[dict]
) -> dict[str, Any]:
    """Compute canonical advisory agreement metrics."""

    # Canonical class sets (per package-version)
    trivy_keys = set((f["canonical_class"], f["pkg_name"], f["version"]) for f in trivy_deduped)
    grype_keys = set((f["canonical_class"], f["pkg_name"], f["version"]) for f in grype_deduped)

    canonical_intersection = trivy_keys & grype_keys
    canonical_union = trivy_keys | grype_keys
    canonical_jaccard = len(canonical_intersection) / len(canonical_union) if canonical_union else 0.0

    # Advisory-only overlap (ignoring package-version)
    trivy_classes = set(f["canonical_class"] for f in trivy_deduped)
    grype_classes = set(f["canonical_class"] for f in grype_deduped)
    class_intersection = trivy_classes & grype_classes
    class_union = trivy_classes | grype_classes
    class_jaccard = len(class_intersection) / len(class_union) if class_union else 0.0

    # Package-PURL overlap
    trivy_purls = set(f["purl"] for f in trivy_deduped if f["purl"])
    grype_purls = set(f["purl"] for f in grype_deduped if f["purl"])
    purl_intersection = trivy_purls & grype_purls

    # Package-version overlap
    trivy_pkgver = set((f["pkg_name"], f["version"]) for f in trivy_deduped)
    grype_pkgver = set((f["pkg_name"], f["version"]) for f in grype_deduped)
    pkgver_intersection = trivy_pkgver & grype_pkgver

    # Severity agreement for canonical matches
    severity_agree = 0
    severity_disagree = 0
    fix_agree = 0
    fix_disagree = 0

    trivy_by_key = {(f["canonical_class"], f["pkg_name"], f["version"]): f for f in trivy_deduped}
    grype_by_key = {(f["canonical_class"], f["pkg_name"], f["version"]): f for f in grype_deduped}

    for key in canonical_intersection:
        tf = trivy_by_key[key]
        gf = grype_by_key[key]
        if tf["severity"] == gf["severity"]:
            severity_agree += 1
        else:
            severity_disagree += 1
        if tf["fixed_version"] and gf["fixed_version"]:
            if tf["fixed_version"] == gf["fixed_version"]:
                fix_agree += 1
            else:
                fix_disagree += 1

    return {
        "trivy_canonical_findings": len(trivy_deduped),
        "grype_canonical_findings": len(grype_deduped),
        "canonical_intersection": len(canonical_intersection),
        "canonical_union": len(canonical_union),
        "canonical_jaccard": round(canonical_jaccard, 4),
        "advisory_class_intersection": len(class_intersection),
        "advisory_class_union": len(class_union),
        "advisory_class_jaccard": round(class_jaccard, 4),
        "purl_intersection": len(purl_intersection),
        "purl_union": len(trivy_purls | grype_purls),
        "pkgver_intersection": len(pkgver_intersection),
        "pkgver_union": len(trivy_pkgver | grype_pkgver),
        "severity_agreement": severity_agree,
        "severity_disagreement": severity_disagree,
        "fix_version_agreement": fix_agree,
        "fix_version_disagreement": fix_disagree,
        "invariant_intersection_le_min": len(canonical_intersection) <= min(len(trivy_deduped), len(grype_deduped)),
        "invariant_jaccard_le_1": canonical_jaccard <= 1.0,
    }


# ===========================================================================
# Main
# ===========================================================================

def main() -> int:
    ts = datetime.now(timezone.utc)
    print(f"[Phase 1] Canonical RQ3 Advisory Equivalence — {ts.isoformat()}")

    # Load raw scanner data
    trivy_data = json.loads((RAW_DIR / "trivy_scan_results.json").read_text(encoding="utf-8"))
    grype_data = json.loads((RAW_DIR / "grype_scan_results.json").read_text(encoding="utf-8"))

    # Build alias graph
    print("[Phase 1] Building alias graph from scanner output...")
    uf = build_alias_graph(trivy_data, grype_data)
    components = uf.get_components()
    print(f"  Connected components: {len(components)}")

    # Assign canonical IDs
    canonical_map: dict[str, str] = {}  # root -> canonical
    class_records = []
    for root, members in components.items():
        canonical = choose_canonical_id(members)
        canonical_map[root] = canonical
        class_records.append({
            "canonical_id": canonical,
            "member_count": len(members),
            "members": sorted(members),
        })

    # Extract and canonicalize findings
    print("[Phase 1] Extracting and canonicalizing findings...")
    trivy_all, grype_all = extract_and_canonicalize(trivy_data, grype_data, uf, canonical_map)
    print(f"  Trivy raw findings: {len(trivy_all)}")
    print(f"  Grype raw findings: {len(grype_all)}")

    # Deduplicate
    trivy_deduped = deduplicate_canonical(trivy_all)
    grype_deduped = deduplicate_canonical(grype_all)
    print(f"  Trivy canonical (deduped): {len(trivy_deduped)}")
    print(f"  Grype canonical (deduped): {len(grype_deduped)}")

    # Compute metrics
    print("[Phase 1] Computing canonical metrics...")
    metrics = compute_canonical_metrics(trivy_deduped, grype_deduped)
    print(f"  Canonical intersection: {metrics['canonical_intersection']}")
    print(f"  Canonical Jaccard: {metrics['canonical_jaccard']}")
    print(f"  Advisory class Jaccard: {metrics['advisory_class_jaccard']}")
    print(f"  Severity agreement: {metrics['severity_agreement']}/{metrics['severity_agreement']+metrics['severity_disagreement']}")

    # Invariant checks
    assert metrics["invariant_intersection_le_min"], \
        f"INVARIANT VIOLATION: intersection {metrics['canonical_intersection']} > min({metrics['trivy_canonical_findings']}, {metrics['grype_canonical_findings']})"
    assert metrics["invariant_jaccard_le_1"], \
        f"INVARIANT VIOLATION: Jaccard {metrics['canonical_jaccard']} > 1.0"
    print("  [OK] All invariants satisfied")

    # Raw primary-ID overlap (for comparison)
    trivy_raw_ids = set(f["primary_id"] for f in trivy_all)
    grype_raw_ids = set(f["primary_id"] for f in grype_all)
    raw_overlap = len(trivy_raw_ids & grype_raw_ids)
    metrics["raw_primary_id_overlap"] = raw_overlap
    metrics["raw_primary_id_jaccard"] = round(
        raw_overlap / len(trivy_raw_ids | grype_raw_ids), 4
    ) if (trivy_raw_ids | grype_raw_ids) else 0.0

    # Save outputs
    print("[Phase 1] Saving outputs...")

    # 1. canonical_alias_classes.csv
    csv_path = OUT_DIR / "canonical_alias_classes.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["canonical_id", "member_count", "members"])
        w.writeheader()
        for rec in sorted(class_records, key=lambda r: r["canonical_id"]):
            w.writerow({
                "canonical_id": rec["canonical_id"],
                "member_count": rec["member_count"],
                "members": "; ".join(rec["members"]),
            })

    # 2. canonical_advisory_agreement.json
    output = {
        "phase": "Phase 1: Canonical RQ3 Advisory Equivalence",
        "timestamp": ts.isoformat(),
        "alias_graph": {
            "total_components": len(components),
            "multi_member_components": sum(1 for c in components.values() if len(c) > 1),
            "singleton_components": sum(1 for c in components.values() if len(c) == 1),
        },
        "metrics": metrics,
        "correction_explanation": (
            "The previous alias-expanded intersection of 66 was invalid because "
            "set expansion adds BOTH identifiers (e.g., CVE-X and GHSA-Y) from each "
            "equivalence class to both expanded sets. When both IDs appear in both "
            "expanded sets, the intersection double-counts the same vulnerability. "
            "The correct metric uses equivalence-class canonicalization: each "
            "vulnerability counts ONCE as a (canonical_class, package, version) tuple."
        ),
    }
    (OUT_DIR / "canonical_advisory_agreement.json").write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # 3. LaTeX table
    generate_latex(metrics, OUT_DIR)

    # 4. Correction markdown
    generate_correction_md(metrics, components, OUT_DIR)

    print(f"[Phase 1] Complete. Outputs in {OUT_DIR}")
    return 0


def generate_latex(metrics: dict, out_dir: Path) -> None:
    """Generate canonical_advisory_agreement.tex."""
    tex = r"""\begin{table}[htbp]
\caption{RQ3 Canonical Advisory Agreement (Corrected)}
\label{tab:rq3-canonical}
\centering\small
\begin{tabular}{lrrrr}
\toprule
\textbf{View} & \textbf{Trivy} & \textbf{Grype} & \textbf{$\cap$} & \textbf{Jaccard} \\
\midrule
"""
    m = metrics
    tex += f"  Raw primary ID & {m['trivy_canonical_findings']} & {m['grype_canonical_findings']} & {m['raw_primary_id_overlap']} & {m['raw_primary_id_jaccard']:.4f} \\\\\n"
    tex += f"  Canonical advisory & {m['trivy_canonical_findings']} & {m['grype_canonical_findings']} & {m['canonical_intersection']} & {m['canonical_jaccard']:.4f} \\\\\n"
    tex += f"  Advisory class only & --- & --- & {m['advisory_class_intersection']} & {m['advisory_class_jaccard']:.4f} \\\\\n"
    tex += f"  Affected PURL & --- & --- & {m['purl_intersection']} & --- \\\\\n"
    tex += f"  Affected (pkg, ver) & --- & --- & {m['pkgver_intersection']} & --- \\\\\n"
    tex += r"""\midrule
  Severity agreement & \multicolumn{4}{l}{"""
    total_sev = m['severity_agreement'] + m['severity_disagreement']
    tex += f"{m['severity_agreement']}/{total_sev}" if total_sev > 0 else "N/A"
    tex += r"""} \\
  Fix-version agreement & \multicolumn{4}{l}{"""
    total_fix = m['fix_version_agreement'] + m['fix_version_disagreement']
    tex += f"{m['fix_version_agreement']}/{total_fix}" if total_fix > 0 else "N/A"
    tex += r"""} \\
\bottomrule
\end{tabular}
\end{table}
"""
    (out_dir / "canonical_advisory_agreement.tex").write_text(tex, encoding="utf-8")


def generate_correction_md(metrics: dict, components: dict, out_dir: Path) -> None:
    """Generate rq3_metric_correction.md."""
    multi = [(choose_canonical_id(m), m) for m in components.values() if len(m) > 1]
    md = f"""# RQ3 Metric Correction: Canonical Advisory Equivalence

## Why the Previous Expanded Intersection of 66 Was Invalid

The Phase 3 alias-expanded overlap reported an intersection of **66 identifiers**
across expanded sets of size 54 (Trivy expanded) and 66 (Grype expanded).

This was **not a valid advisory-count metric** because:

1. **Double-counting**: When a vulnerability has both CVE-2023-37920 and
   GHSA-xqr8-7jwr-rhp7, alias expansion adds BOTH to each scanner's expanded
   set. The intersection then counts both IDs as separate matches, but they
   represent **the same vulnerability**.

2. **Inflation beyond finding count**: An intersection of 66 exceeds the raw
   finding count of both scanners (Trivy=54, Grype=35). This is mathematically
   impossible for a count of distinct advisories.

3. **Correct interpretation**: The expanded intersection of 66 counts
   *identifier strings* that appear in both expanded sets, not distinct
   vulnerability equivalence classes.

## Corrected Approach: Equivalence-Class Canonicalization

Each vulnerability gets one **canonical class ID** via union-find on the
alias graph. Each (canonical_class, package, version) tuple counts **once**.

## Corrected Metrics

| Metric | Value |
|--------|-------|
| Trivy canonical findings | {metrics['trivy_canonical_findings']} |
| Grype canonical findings | {metrics['grype_canonical_findings']} |
| Canonical intersection | {metrics['canonical_intersection']} |
| Canonical Jaccard | {metrics['canonical_jaccard']:.4f} |
| Advisory class intersection | {metrics['advisory_class_intersection']} |
| Advisory class Jaccard | {metrics['advisory_class_jaccard']:.4f} |
| Severity agreement | {metrics['severity_agreement']}/{metrics['severity_agreement']+metrics['severity_disagreement']} |

## Invariants Verified

- canonical_intersection ({metrics['canonical_intersection']}) <= min(trivy={metrics['trivy_canonical_findings']}, grype={metrics['grype_canonical_findings']})
- canonical_jaccard ({metrics['canonical_jaccard']}) <= 1.0
- Each equivalence class counted once per (package, version)

## Multi-Member Equivalence Classes

"""
    for canonical, members in sorted(multi, key=lambda x: x[0]):
        md += f"- **{canonical}**: {', '.join(sorted(members))}\n"

    (out_dir / "rq3_metric_correction.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
