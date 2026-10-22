# RQ3 Metric Correction: Canonical Advisory Equivalence

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
| Trivy canonical findings | 54 |
| Grype canonical findings | 35 |
| Canonical intersection | 35 |
| Canonical Jaccard | 0.6481 |
| Advisory class intersection | 35 |
| Advisory class Jaccard | 0.6481 |
| Severity agreement | 35/35 |

## Invariants Verified

- canonical_intersection (35) <= min(trivy=54, grype=35)
- canonical_jaccard (0.6481) <= 1.0
- Each equivalence class counted once per (package, version)

## Multi-Member Equivalence Classes

- **CVE-2021-33503**: CVE-2021-33503, GHSA-q2q7-5pp4-w6pg
- **CVE-2022-22817**: CVE-2022-22817, GHSA-8vj2-vxx3-667w
- **CVE-2022-23491**: CVE-2022-23491, GHSA-43fp-rhv2-5gv8
- **CVE-2022-24303**: CVE-2022-24303, GHSA-9j59-75qj-795w
- **CVE-2022-40897**: CVE-2022-40897, GHSA-r9hx-vwmv-q579
- **CVE-2022-45198**: CVE-2022-45198, GHSA-m2vv-5vj5-2hm7
- **CVE-2023-0286**: CVE-2023-0286, GHSA-x4qr-2fvf-3mr5
- **CVE-2023-23931**: CVE-2023-23931, GHSA-w7pp-m8wf-vj6r
- **CVE-2023-32681**: CVE-2023-32681, GHSA-j8r2-6x86-q33q
- **CVE-2023-37920**: CVE-2023-37920, GHSA-xqr8-7jwr-rhp7
- **CVE-2023-43804**: CVE-2023-43804, GHSA-v845-jxx5-vc9f
- **CVE-2023-44271**: CVE-2023-44271, GHSA-8ghj-p4vj-mr35
- **CVE-2023-45803**: CVE-2023-45803, GHSA-g4mx-q9vg-27p4
- **CVE-2023-4863**: CVE-2023-4863, GHSA-j7hp-h8jx-5ppr
- **CVE-2023-49083**: CVE-2023-49083, GHSA-jfhm-5ghh-2f97
- **CVE-2023-50447**: CVE-2023-50447, GHSA-3f63-hfp8-52jq
- **CVE-2023-50782**: CVE-2023-50782, GHSA-3ww4-gg4f-jr7f
- **CVE-2024-0727**: CVE-2024-0727, GHSA-9v9h-cgj8-h64p
- **CVE-2024-26130**: CVE-2024-26130, GHSA-6vqw-3v5j-54x4
- **CVE-2024-28219**: CVE-2024-28219, GHSA-44wm-f244-xhp3
- **CVE-2024-35195**: CVE-2024-35195, GHSA-9wx4-h78v-vm56
- **CVE-2024-37891**: CVE-2024-37891, GHSA-34jh-p97f-mpxf
- **CVE-2024-39689**: CVE-2024-39689, GHSA-248v-346w-9cwc
- **CVE-2024-47081**: CVE-2024-47081, GHSA-9hjg-9r4m-mvj7
- **CVE-2024-6345**: CVE-2024-6345, GHSA-cx63-2mw6-8hw5
- **CVE-2025-47273**: CVE-2025-47273, GHSA-5rjg-fvgr-3xxf
- **CVE-2025-50181**: CVE-2025-50181, GHSA-pq67-6m6q-mj2v
- **CVE-2025-66418**: CVE-2025-66418, GHSA-gm62-xv2j-4w53
- **CVE-2025-66471**: CVE-2025-66471, GHSA-2xpw-w6gg-jr37
- **CVE-2026-21441**: CVE-2026-21441, GHSA-38jv-5279-wg99
- **CVE-2026-25645**: CVE-2026-25645, GHSA-gc5v-m9x4-r6x2
- **CVE-2026-26007**: CVE-2026-26007, GHSA-r6ph-v2qm-q3c2
- **CVE-2026-34073**: CVE-2026-34073, GHSA-m959-cc7f-wv43
- **CVE-2026-42308**: CVE-2026-42308, GHSA-wjx4-4jcj-g98j
- **CVE-2026-42310**: CVE-2026-42310, GHSA-r73j-pqj5-w3x7
- **CVE-2026-44431**: CVE-2026-44431, GHSA-qccp-gfcp-xxvc
- **CVE-2026-54058**: CVE-2026-54058, GHSA-62p4-gmf7-7g93
- **CVE-2026-54059**: CVE-2026-54059, GHSA-8v84-f9pq-wr9x
- **CVE-2026-54060**: CVE-2026-54060, GHSA-5x94-69rx-g8h2
- **CVE-2026-55379**: CVE-2026-55379, GHSA-45hq-cxwh-f6vc
- **CVE-2026-55380**: CVE-2026-55380, GHSA-phj9-mv4w-65pm
- **CVE-2026-55798**: CVE-2026-55798, GHSA-4x4j-2g7c-83w6
- **CVE-2026-59197**: CVE-2026-59197, GHSA-xj96-63gp-2gmr
- **CVE-2026-59198**: CVE-2026-59198, GHSA-fj7v-r99m-22gq
- **CVE-2026-59199**: CVE-2026-59199, GHSA-6r8x-57c9-28j4
- **CVE-2026-59200**: CVE-2026-59200, GHSA-jjj6-mw9f-p565
- **CVE-2026-59204**: CVE-2026-59204, GHSA-vjc4-5qp5-m44j
- **CVE-2026-59205**: CVE-2026-59205, GHSA-9hw9-ch79-4vh6
- **CVE-2026-59890**: CVE-2026-59890, GHSA-h35f-9h28-mq5c
