# Publication Readiness Report

**Generated:** 2026-07-22T17:16:29.601764+00:00
**Profile:** local

## Summary

| Status | Count |
|--------|-------|
| SUPPORTED | 0 |
| SUPPORTED_QUICK_ONLY | 3 |
| PARTIALLY_SUPPORTED | 0 |
| UNSUPPORTED | 1 |
| BLOCKED_EXTERNAL_INFRASTRUCTURE | 4 |
| BLOCKED_GPU | 1 |

## Claims Matrix

| Claim | RQ | Status |
|-------|-----|--------|
| BOM representation coverage of ground-truth graph | RQ1 | **SUPPORTED_QUICK_ONLY** |
| Cryptographic tamper detection across supply-chain scenarios | RQ2 | **SUPPORTED_QUICK_ONLY** |
| Scanner agreement and VEX triage effectiveness | RQ3 | **SUPPORTED_QUICK_ONLY** |
| Runtime overhead and drift detection | RQ4 | **UNSUPPORTED** |
| GPU utilization and memory metrics | RQ4 | **BLOCKED_GPU** |
| Harbor OCI storage and signature distribution | RQ2 | **BLOCKED_EXTERNAL_INFRASTRUCTURE** |
| Dependency-Track BOM/VEX ingestion and processing | RQ3 | **BLOCKED_EXTERNAL_INFRASTRUCTURE** |
| Kubernetes/OBOM runtime observation | RQ4 | **BLOCKED_EXTERNAL_INFRASTRUCTURE** |
| Industrial deployment end-to-end pipeline | ALL | **BLOCKED_EXTERNAL_INFRASTRUCTURE** |

## Key Blockers

- **RQ4 Availability**: Campaign uses simulated inference — requires real HTTP calls to live service
- **GPU**: No NVIDIA GPU available on this host
- **Industrial infrastructure**: Harbor, Dependency-Track, GitLab, K3s not configured

## Supported Claims (Quick Campaign)

- RQ1: BOM coverage computed from real Syft/Trivy/TraceAI output
- RQ2: Tamper detection with real SHA-256, ECDSA, policy engine
- RQ3: Scanner comparison with real Trivy/Grype output + VEX policy evaluation