# RQ3 Summary: Trivy vs Grype Scanner Agreement

**Audit status:** OBSERVED FROM RAW DATA + DERIVED  
**Primary source:** `results/rq3/rq3-20260722-140819-082e9531/` (article campaign)  
**Correction source:** `generated/rq3/canonical_advisory_agreement.json`

---

## 1. Campaign Identity

| Property | Value | Source |
|----------|-------|--------|
| Campaign ID | rq3-20260722-140819-082e9531 | `rq3_summary.json` (OBSERVED) |
| Timestamp | 2026-07-22T17:08:22 | `rq3_summary.json` (OBSERVED) |
| Profile | local | `rq3_summary.json` (OBSERVED) |
| Scanner A | **Trivy 0.72.0** | `results_manifest.json` → `tools.trivy` (OBSERVED) |
| Scanner B | **Grype 0.86.1** | `tool_versions.json` → `grype.version` (OBSERVED) |
| Trivy DB version | 2 | `database_metadata.json` → `scanners.trivy.db_version` (OBSERVED) |
| Trivy DB updated | 2026-07-22T13:17:28Z | `database_metadata.json` (OBSERVED) |
| Grype DB updated | NOT RECORDED | `database_metadata.json` → `db_updated_at: ""` (NOT AVAILABLE) |
| Scan timestamp (Trivy) | 2026-07-22T17:08:19 | `database_metadata.json` (OBSERVED) |
| Scan timestamp (Grype) | 2026-07-22T17:08:20 | `database_metadata.json` (OBSERVED) |

**Note on Trivy version:** `tool_versions.json` records that Trivy download failed (404) at v0.58.2. The Trivy binary in `.tools/bin/trivy.exe` was present and the probe reports version 0.72.0. The article's `results_manifest.json` uses `"trivy": "0.72.0"`. This version is used throughout.

---

## 2. Scan Target

Scan target: `fixtures/vulnerable_project/vulnerable_sbom.cdx.json` (CycloneDX SBOM, 1601 bytes)  
Source: INFERRED FROM CODE (`src/traceai/campaigns/rq3.py` scans the vulnerable project SBOM)  
The SBOM contains vulnerable versions of: certifi, cryptography, pillow, requests, setuptools, urllib3.

---

## 3. Raw Scanner Findings

Source: `scanner_findings_normalized.csv` (89 rows) + `scanner_agreement.csv` (OBSERVED FROM RAW DATA)

| Metric | Value |
|--------|-------|
| **Trivy total findings** | **54** |
| **Grype total findings** | **35** |
| Raw intersection | 4 |
| Raw union | 85 |
| Trivy-only | 50 |
| Grype-only | 31 |
| **Raw Jaccard** | **0.0471** |

---

## 4. Packages Affected

Both scanners identify vulnerabilities in exactly the same 6 packages:

| Package | Version scanned | Trivy findings | Grype findings |
|---------|----------------|---------------|---------------|
| certifi | 2022.9.24 | 3 | ? (subset of 35) |
| cryptography | 39.0.0 | 16 | ? |
| pillow | 9.0.0 | ~20 | ? |
| requests | (vulnerable version) | ? | ? |
| setuptools | (vulnerable version) | ? | ? |
| urllib3 | (vulnerable version) | ? | ? |

Note: Per-package breakdown for Grype not independently computed here; both scanner sets share the same 6 package PURLs (purl_intersection=6, purl_union=6, jaccard_purl=1.0 — OBSERVED from `canonical_advisory_agreement.json`).

---

## 5. Severity Distribution

Source: DERIVED from `scanner_findings_normalized.csv`

| Severity | Trivy | Grype |
|---------|-------|-------|
| CRITICAL | 2 | 2 |
| HIGH | 30 | 18 |
| MEDIUM | 17 | 11 |
| LOW | 5 | 4 |
| **Total** | **54** | **35** |

---

## 6. Why Raw Jaccard = 0.0471

The raw intersection of only 4 findings occurs because:

1. **ID namespace difference:** Trivy primarily reports CVE IDs (e.g., CVE-2023-37920), while Grype primarily reports GHSA IDs (e.g., GHSA-xqr8-7jwr-rhp7) for the same vulnerabilities. The 4 intersection items are all GHSA IDs that both scanners happened to use.

2. **Advisory alias structure:** Most vulnerabilities have both a CVE ID and a GHSA ID. Trivy records the CVE as the primary ID; Grype records the GHSA as the primary ID.

Source: `generated/rq3/phase3_agreement/` — stages 2-4 progressively apply alias resolution:
- Stage 2 (raw ID overlap): 4
- Stage 3 (alias-expanded): 66 IDs (later corrected — see §7)
- Stage 4 (PURL overlap): 6
- Stage 5 (pkg@ver overlap): 6

---

## 7. Canonical Advisory Jaccard (Corrected)

Source: `generated/rq3/canonical_advisory_agreement.json` + `generated/rq3/rq3_metric_correction.md`

| Metric | Value |
|--------|-------|
| Trivy canonical findings | 54 |
| Grype canonical findings | 35 |
| Canonical intersection | **35** |
| Canonical union | **54** |
| **Canonical Jaccard** | **0.6481** |

**Correction rationale:** The alias-expanded intersection of 66 (Stage 3) was invalid because set expansion adds both CVE-X and GHSA-Y to each scanner's set. If both appear in both expanded sets, the intersection double-counts them. The correct approach (union-find equivalence classes) assigns each vulnerability exactly one canonical ID. The corrected intersection is 35 (all Grype findings map to canonical classes present in Trivy). The canonical union is 54 (all Trivy findings) because Trivy is a strict superset of Grype under canonicalization.

**Interpretation:** After canonical normalization, Grype finds 35 vulnerabilities all of which are also found by Trivy. Trivy finds 19 additional vulnerabilities (54-35=19) not found by Grype — these are the genuine database coverage differences.

---

## 8. Disagreement Taxonomy

Source: `generated/rq3/phase3_agreement/rq3_agreement_summary.json`

| Category | Count | Scanner |
|---------|-------|---------|
| ADVISORY_ALIAS_RESOLVED (same vuln, different ID) | 31 | Trivy-only |
| ID_NAMESPACE_DIFFERENCE | 18 | Trivy-only |
| DATABASE_COVERAGE_GAP | 1 | Trivy-only |
| ADVISORY_ALIAS_RESOLVED (same vuln, GHSA reported only by Grype) | 31 | Grype-only |

---

## 9. VEX Conformance Results

Source: `results/rq3/rq3-20260722-140819-082e9531/vex_decisions.csv` (OBSERVED FROM RAW DATA)

| Scenario | Expected Decision | Actual | Pass |
|---------|-----------------|--------|------|
| V0 — no_vex_baseline | VEX_MALFORMED | VEX_MALFORMED | True |
| V1 — valid_not_affected | APPROVED | APPROVED | True |
| V2 — wrong_component_linkage | VEX_WRONG_COMPONENT | VEX_WRONG_COMPONENT | True |
| V3 — unsigned_local_profile | APPROVED | APPROVED | True |
| V4 — expired_vex_document | VEX_EXPIRED | VEX_EXPIRED | True |
| V5 — under_investigation | APPROVED | APPROVED | True |
| V6 — affected_with_workaround | APPROVED | APPROVED | True |
| V7 — fixed_version_inconsistent | APPROVED | APPROVED | True |

**VEX conformance: 8/8 (100%)** — OBSERVED FROM RAW DATA

---

## 10. Property-Based VEX Tests

Source: `generated/rq3/vex_property_cases.csv` (OBSERVED FROM RAW DATA)

| Metric | Value |
|--------|-------|
| Total cases | 500 |
| Seed | 42 |
| Framework | `random.Random(42)` — **NOT Hypothesis** |
| Agreement rate | 1.0000 |
| Counterexamples | 0 |

**Important note on tooling:** The file `src/traceai/campaigns/vex_property.py` imports no `hypothesis` module. The docstring mentions "VEX property-based testing using Hypothesis" but the implementation uses `random.Random(seed)`. This is documented as intentional: "Uses a simple PRNG-based generator (not Hypothesis) for full reproducibility without test-framework dependency at runtime." The article must not claim Hypothesis is used.

---

## 11. Article-Ready Numbers Table

| Metric | Value | Source type |
|--------|-------|------------|
| Trivy total findings | 54 | OBSERVED |
| Grype total findings | 35 | OBSERVED |
| Raw Jaccard | 0.0471 | DERIVED |
| Canonical Jaccard | 0.6481 | DERIVED (post-processing) |
| Packages affected (both) | 6 | DERIVED |
| VEX conformance | 8/8 | OBSERVED |
| Property-based cases | 500 | OBSERVED |
| Counterexamples | 0 | OBSERVED |
