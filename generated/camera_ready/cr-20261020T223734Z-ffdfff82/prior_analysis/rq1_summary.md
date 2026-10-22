# RQ1 Summary: 93.1% Representation Coverage

**Audit status:** VERIFIED FROM SOURCE FILES  
**Primary source:** `generated/rq1/final_rq1_summary.tex`, `generated/article/results_manifest.json`  
**Ground-truth source:** `results/rq1/rq1-20260722-140850-18433df2/ground_truth_graph.json`

---

## 1. Origin of the 93.1% Number

**OBSERVED:** The value `0.931` appears in:
- `generated/article/results_manifest.json` → key `rq1.composite_coverage` = 0.931 (OBSERVED)
- `generated/rq1/final_rq1_summary.tex` → "Composite coverage: 0.931 (27/29)" (OBSERVED)
- `generated/article/claims_matrix_final.csv` → "Composite 0.931; 2 HBOM nodes unmatched" (OBSERVED)

**The 93.1% is NOT the raw campaign output.** It is the output of `src/traceai/campaigns/rq1_finalizer.py`, which runs AFTER the raw campaign and generates a more complete BOM by:
1. Rebuilding the ground-truth with full typed nodes
2. Generating a complete ML-BOM (`generated/rq1/final_ml_bom.cdx.json`)
3. Generating an observed OBOM (`generated/rq1/final_obom.cdx.json`)
4. Using real Syft output from the installed environment

**The raw campaign output** (`results/rq1/rq1-20260722-140850-18433df2/rq1_results.csv`) reports `composite_coverage=0.1724` — this is the unaided scanner coverage (Trivy/Syft timed out during that run; syft.cdx.json = 0 bytes).

---

## 2. N_inventory and N_represented

### Ground-Truth Graph
- **Total nodes in ground-truth:** 31 (source: `ground_truth_graph.json` → `meta.total_nodes`)
- **NOT_APPLICABLE nodes:** 2 (host-gpu, cuda-runtime)
- **N_inventory = applicable nodes:** **29** (source: `ground_truth_graph.json` → `meta.applicable_nodes` = 29)

### Finalizer Coverage (article-reported)
- **N_represented:** **27** (derived: 0.931 × 29 = 27.0)
- **N_unmatched:** **2** (source: `generated/rq1/unmatched_nodes_after.csv` — os-platform, host-cpu)
- **TC = N_represented / N_inventory = 27/29 = 0.9310...** (rounded to 0.931)

### Verification
```
TC = 27 / 29 = 0.93103... ≈ 0.931  ✓
```

---

## 3. Coverage by Domain (from finalizer)

Source: `generated/rq1/final_metrics.json`

| Asset class | Reference assets (applicable) | Represented | Coverage |
|-------------|-------------------------------|-------------|----------|
| ML-BOM (model + artifacts) | 6 | 6 | 1.000 |
| SBOM (software packages) | 16 | 16 | 1.000 |
| HBOM (hardware + runtime) | 4 | 2 | **0.500** |
| OBOM (operational services) | 3 | 3 | 1.000 |
| **Total (applicable)** | **29** | **27** | **0.931** |

**Note on ground-truth discrepancy:** The raw campaign file (`ground_truth_graph.json`) lists `sbom.applicable=17`, while the finalizer reports `sbom.applicable=16`. The difference is `traceai-app` (id=`traceai-app`), which appears in the raw ground-truth as an SBOM + OBOM node, but in the finalizer it is absorbed into `inference-service` (OBOM only). The finalizer's 16 SBOM nodes are the direct Python dependencies from `requirements-exact.txt`.

---

## 4. Breakdown of the 6.9% Not Represented (2/29)

Source: `generated/rq1/unmatched_nodes_after.csv`

| Node ID | Type | Name | Domain | Reason |
|---------|------|------|--------|--------|
| `os-platform` | runtime | Windows | HBOM | Not represented as named CycloneDX component; noted as representable via `type=operating-system` property |
| `host-cpu` | hardware | CPU (12P/14T Intel) | HBOM | Hardware node not directly in current BOM schema; CPU info captured as properties, not first-class node |

Both nodes are **CycloneDX-representable** (see `generated/rq1/domain_reclassification_notes.md`). The gap is an implementation choice, not a specification limitation.

---

## 5. Scope: NOT_APPLICABLE Nodes

| Node ID | Type | Reason |
|---------|------|--------|
| `host-gpu` | hardware | No NVIDIA GPU on this host (`gpu_available=false` in ground-truth meta) |
| `cuda-runtime` | runtime | GPU unavailable; CUDA runtime = N/A |

These 2 nodes are **excluded from both numerator and denominator**. This is correct methodology: measuring coverage on a local CPU-only run should not be penalized for absent hardware.

---

## 6. Exact Source of Each Number

| Claim | Value | Source | Data Type |
|-------|-------|--------|-----------|
| N_inventory (applicable) | 29 | `ground_truth_graph.json` → `meta.applicable_nodes` | OBSERVED |
| N_represented | 27 | `final_rq1_summary.tex` (27/29) | OBSERVED |
| TC | 0.931 | `results_manifest.json` → `rq1.composite_coverage` | OBSERVED |
| ML-BOM coverage | 1.000 (6/6) | `final_metrics.json` → `domain_coverage.mlbom` | OBSERVED |
| SBOM coverage | 1.000 (16/16) | `final_metrics.json` → `domain_coverage.sbom` | OBSERVED |
| HBOM coverage | 0.500 (2/4) | `final_metrics.json` → `domain_coverage.hbom` | OBSERVED |
| OBOM coverage | 1.000 (3/3) | `final_metrics.json` → `domain_coverage.obom` | OBSERVED (3 nodes in finalizer) |
| Raw campaign composite | 0.1724 | `rq1_results.csv` → row `composite_coverage` | OBSERVED |
| Syft components (full) | 108 | `final_metrics.json` → `syft_components` | OBSERVED |
| Trivy components (probe) | 18–23 | `final_metrics.json` → `trivy_components_probe` | OBSERVED |

---

## 7. Important Distinction: Inventory Coverage ≠ Security Coverage

**Inventory coverage (TC = 93.1%)** measures whether known supply-chain components are *representable* in a CycloneDX AI/ML-BOM. It answers: "Are the 29 required artifacts at least present as identifiable nodes in the BOM graph?"

**Security coverage** would measure whether:
- Artifact digests are attested (RQ2)
- Vulnerabilities in represented components are scanned (RQ3)
- Runtime configuration matches the approved BOM (RQ4)

A component that is *represented* in the BOM (counted in TC) can still be:
- Unattested (no signature, no digest check)
- Vulnerable (not yet scanned or triaged)
- Drifted at runtime (configuration changed after attestation)

The 2 unrepresented HBOM nodes (os-platform, host-cpu) have NO cryptographic attestation mechanism regardless — their absence from the BOM means zero security coverage for those nodes, not just 0 inventory coverage.

---

## 8. Paper-Ready Coverage Table

Source: `generated/rq1/final_metrics.json` + `generated/article/results_manifest.json`

| Asset class | Reference assets | Represented | Coverage |
|-------------|-----------------|-------------|---------|
| Model artifacts (ML-BOM) | 3 | 3 | 100% |
| Tokenizer artifacts (ML-BOM) | 1 | 1 | 100% |
| Dataset / configuration (ML-BOM) | 2 | 2 | 100% |
| Software packages (SBOM) | 16 | 16 | 100% |
| Hardware (HBOM) | 2 | 1 (RAM only) | 50% |
| Runtime/OS (HBOM) | 2 | 1 (Python only) | 50% |
| Operational services (OBOM) | 3 | 3 | 100% |
| **Total (applicable)** | **29** | **27** | **93.1%** |

Note: HBOM 4 nodes (python-runtime, os-platform, host-cpu, host-ram): 2 represented (python-runtime, host-ram), 2 unrepresented (os-platform, host-cpu).

---

## 9. HBOM Gap: CycloneDX Representability Analysis

**Question:** Are `os-platform` and `host-cpu` representable in CycloneDX, or is the gap a specification limitation?

**Answer: REPRESENTABLE BUT NOT REPRESENTED AS FIRST-CLASS COMPONENTS.**

Evidence from `generated/rq1/domain_reclassification_notes.md` and `generated/rq1/final_obom.cdx.json`:

| Node | CycloneDX type available | Current representation | First-class? |
|------|-------------------------|----------------------|--------------|
| os-platform (Windows 10.0.26200) | `type=operating-system` (valid in CycloneDX 1.4+) | Exists as bom-ref=obom-os in final_obom.cdx.json with name=windows, version=10.0.26200 | YES — it IS present in final_obom.cdx.json |
| host-cpu (Intel64 12P/14T) | `type=device` (valid) | Exists as bom-ref=obom-cpu with properties traceai:processor, traceai:architecture | YES — it IS present as properties-only device |

**Re-examination finding:** The `generated/rq1/final_obom.cdx.json` actually DOES contain both `obom-os` and `obom-cpu` as CycloneDX components. However, `generated/rq1/unmatched_nodes_after.csv` lists them as unmatched.

**Root cause of discrepancy:** The coverage computation in `rq1_finalizer.py` computes domain coverage by matching ground-truth node names against BOM component names. The ground-truth nodes `os-platform` (name="Windows") and `host-cpu` (name="cpu") use simplified names that do not match the CycloneDX component names in `final_obom.cdx.json` (name="windows" and name="cpu" respectively — these should match, but coverage may use a strict string comparison).

**Conservative position for paper:** The `unmatched_nodes_after.csv` records these 2 nodes as unmatched — this is the evidence the 93.1% figure rests on. Whether the mismatch is a naming collision in the coverage script or a genuine absence in the BOM, the reported 93.1% is based on the unmatched-node output.

**CycloneDX specification verdict:** Both OS platform and CPU are fully representable in CycloneDX. The gap reflects either a coverage-script name-matching issue or an incomplete property-only representation (not a dedicated CycloneDX node for purpose of coverage counting). This is an implementation choice, NOT a CycloneDX specification limitation.

---

## 10. Methodological Notes

1. **The 93.1% is computed by the finalizer, not the raw campaign.** The raw campaign reported 17.24% because Syft timed out (120s timeout) and Trivy found 0 components due to a format mismatch with `requirements.lock`. The finalizer uses a separate Syft invocation (`generated/rq1/syft_direct.cdx.json`, 493 KB) against `requirements-exact.txt`.

2. **Trivy limitation documented:** `results/rq1/rq1-20260722-140850-18433df2/rq1_summary.json` → `metrics.trivy.status = "TOOL_LIMITATION"`. Trivy fs scan cannot process `requirements.lock` (pip freeze format). Trivy probe against `requirements-exact.txt` finds 18–23 components (`final_metrics.json` → `trivy_components_probe`).

3. **HBOM 0.5 coverage:** The ground-truth has 4 HBOM applicable nodes (python-runtime, os-platform, host-cpu, host-ram). The finalizer represents python-runtime and host-ram but not os-platform (reclassified as OS software, not hardware) and not host-cpu (properties only). This gives 2/4 = 0.50.

4. **OBOM 3 nodes in finalizer vs 3 in ground-truth:** The finalizer adds `runtime-snapshot` as the third OBOM node (psutil observation), while the raw ground-truth had `traceai-app` as the third OBOM node.
