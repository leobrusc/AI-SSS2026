# TraceAI Evidence Audit Report

**Generated:** 2026-07-22T16:01:12.270583+00:00
**Profile:** local

## Git Status

- Commit: `HEAD`
- Branch: `main`
- Uncommitted files: 27

## Python Environment

- Version: 3.11.6
- In venv: True
- Packages: 85

## Test Results

- unit: 42 passed, 0 failed (exit 0)
- integration: 8 passed, 0 failed (exit 0)

## Evidence Classification

| Component | Classification |
|-----------|---------------|
| availability_campaign | **MOCK_ONLY** |
| bom_generation | **CONTROLLED_FIXTURE** |
| inference_engine | **REAL_EVIDENCE** |
| integration_tests | **REAL_EVIDENCE** |
| lineage_availability_campaigns | **MOCK_ONLY** |
| lineage_security_campaigns | **REAL_EVIDENCE** |
| model_availability | **NOT_IMPLEMENTED** |
| publication_tables | **UNVERIFIED** |
| security_campaign | **REAL_EVIDENCE** |
| unit_tests | **REAL_EVIDENCE** |
| vulnerability_scanning | **NOT_IMPLEMENTED** |

## Classification Counts

- CONTROLLED_FIXTURE: 1
- MOCK_ONLY: 2
- NOT_IMPLEMENTED: 2
- REAL_EVIDENCE: 5
- UNVERIFIED: 1

## Mock Detection Findings

### availability_campaign
- Classification: **MOCK_ONLY**
- Detail: Availability campaign uses _simulate_request() which generates synthetic latency via random.gauss(). No actual HTTP calls to the inference service. Observations are NOT from real model inference.

### vulnerability_scanning
- Classification: **NOT_IMPLEMENTED**
- Detail: Scanner integration code exists but tools are not installed. No actual scanner output has been produced. RQ3 evidence is missing.

### publication_tables
- Classification: **UNVERIFIED**
- Detail: Tables are generated from analysis_results.json which is computed from raw campaign files. Availability data traces to synthetic observations (MOCK_ONLY). Security data traces to real policy evaluation (REAL_EVIDENCE).
