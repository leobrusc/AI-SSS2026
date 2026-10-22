# Fresh historical scanner recomputation
Raw source: `results\rq3\rq3-20260722-140819-082e9531\raw`. Raw finding records: Trivy 54, Grype 35.
[
  {
    "basis": "raw_package_version_advisory",
    "trivy": 54,
    "grype": 35,
    "intersection": 4,
    "union": 85,
    "trivy_only": 50,
    "grype_only": 31,
    "jaccard": 0.047058823529411764
  },
  {
    "basis": "canonical_package_version_advisory",
    "trivy": 54,
    "grype": 35,
    "intersection": 35,
    "union": 54,
    "trivy_only": 19,
    "grype_only": 0,
    "jaccard": 0.6481481481481481
  },
  {
    "basis": "raw_advisory_only",
    "trivy": 54,
    "grype": 35,
    "intersection": 4,
    "union": 85,
    "trivy_only": 50,
    "grype_only": 31,
    "jaccard": 0.047058823529411764
  }
]
Deduplication: set of (PEP503 normalized Python package name, exact installed version, advisory id).
Alias normalization: union-find using ONLY Trivy VendorIDs and Grype relatedVulnerabilities.
Each equivalence class counted once per package/version. Canonical ID prefers CVE then GHSA.
PURLs retained in raw scanner files; this matching rule uses package/version, not claimed universal PURL equivalence.
Embedded scanner metadata copied to generated/camera_ready/cr-20261020T223734Z-ffdfff82/scanner_embedded_metadata.json.
Exact historical tool and DB metadata absent from embedded fields must be marked unavailable; current versions cannot replace historical versions.
Do not infer agreement from record totals or inflate intersection by counting both GHSA and CVE aliases.

Historical embedded tool/DB metadata: Trivy 0.72.0; created 2026-07-22T14:08:20.1579099-03:00; Trivy DB timestamp/version NOT RECORDED in report. Grype 0.86.1; {"built": "2026-03-09T00:31:20Z", "schemaVersion": 5, "location": "C:\\Users\\leolima\\AppData\\Local\\cache/grype/db/5", "checksum": "sha256:a65e27aecbbb2cd6671f5da84c16db7e9c60f0114075e6ae9bcc71f466460a0c", "error": null}; scan timestamp 2026-07-22T14:08:22.0044087-03:00. Target: CycloneDX vulnerable-project fixture, not deployed production environment.
