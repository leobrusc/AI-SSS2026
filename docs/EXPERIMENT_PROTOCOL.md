> Historical instructions retained for provenance. For AI-SSS 2026 use README.md and docs/A100_RQ4_RUNBOOK.md with uv.

# TraceAI Experiment Protocol

## Overview

This document defines the full experiment protocol for the TraceAI LADC 2026 study. The protocol is structured in six phases (0–5), spanning environment preparation through statistical analysis and publication artifact generation.

---

## Research Questions

| ID  | Question |
|-----|----------|
| RQ1 | How completely can automated CycloneDX generators capture the ground-truth dependency graph of an LLM inference pipeline? |
| RQ2 | Can cryptographic provenance and attestation gates detect integrity violations across model, data, and infrastructure supply-chain scenarios? |
| RQ3 | How effectively do CycloneDX VEX documents reduce actionable vulnerability alerts while preserving detection of genuine risks? |
| RQ4 | What is the runtime overhead and fault-detection capability of configuration-aware controls in a containerized LLM service? |

---

## Phase Structure

### Phase 0 — Environment Preparation

**Objective**: Establish a reproducible, verified execution environment.

**Steps**:
1. Run `traceai doctor --profile {profile}` to generate `environment.json`
2. Verify Python version (3.10–3.12), venv activation, and dependency installation
3. Download and verify model weights against `model.lock.json`
4. Install and verify external tools against `tools.lock.json`
5. Validate GPU availability and VRAM (if applicable)
6. Capture baseline system metrics (CPU, RAM, disk)

**Exit Criteria**: `environment.json` exists, all checks pass, model loaded successfully.

### Phase 1 — BOM Generation and Ground-Truth (RQ1)

**Objective**: Generate CycloneDX AI/ML BOMs and compare against ground truth.

**Steps**:
1. Run `traceai bom --profile {profile}` to generate the CycloneDX BOM
2. Construct ground-truth dependency graph from:
   - `pip freeze` (Python packages)
   - Model card metadata (model components)
   - Tokenizer files and revision
   - Dataset manifests
   - System libraries (torch backends)
3. Compare generated BOM against ground truth
4. Measure completeness (components found / total components)
5. Record per-category recall (ML-model, ML-dataset, library, framework)

**Deliverables**: `generated/bom-{profile}.cdx.json`, `results/raw/bom-completeness.json`

### Phase 2 — Security Campaign (RQ2 + RQ3)

**Objective**: Validate that provenance gates detect supply-chain attacks and VEX processing is correct.

**Steps**:
1. Establish approved baseline (S0): sign artifacts, create attestation, verify gate APPROVED
2. For each security scenario (S1–S5, S8–S10):
   a. Inject fault into workspace copy
   b. Evaluate deployment gate
   c. Record decision (expected: DENIED with specific reason code)
   d. Restore workspace
3. Repeat for N trials (30 full, 3 quick)
4. Record per-scenario detection rate and false positive/negative counts

**Deliverables**: `results/raw/security-{timestamp}/trial-{N}.json`

### Phase 3 — Availability Campaign (RQ4)

**Objective**: Measure runtime control effectiveness under load and fault conditions.

**Steps**:
1. Start inference service with configuration C0–C3
2. For each availability scenario (S6–S7, S11):
   a. Apply configuration or load condition
   b. Send request workload (200 requests/trial full, 20 quick)
   c. Measure latency (P50, P95, P99), throughput, error rates
   d. Verify drift detection and circuit breaker behavior
3. Repeat for N trials
4. Record telemetry snapshots per trial

**Deliverables**: `results/raw/availability-{timestamp}/trial-{N}.json`

### Phase 4 — Overhead Campaign

**Objective**: Quantify the performance cost of BOM generation, signing, and policy evaluation.

**Steps**:
1. Measure BOM generation time (wall-clock, per component)
2. Measure signing and attestation creation time
3. Measure policy engine evaluation time
4. Measure per-request overhead of configuration digest verification
5. Compare baseline (no controls) vs full-protection (C3)

**Deliverables**: `results/raw/overhead-{timestamp}/trial-{N}.json`

### Phase 5 — Analysis and Publication Artifacts

**Objective**: Produce statistically sound results and publication-ready artifacts.

**Steps**:
1. Load all raw results from `results/raw/`
2. Compute statistics (see Statistical Analysis section below)
3. Generate LaTeX tables for paper inclusion
4. Generate matplotlib figures
5. Produce narrative fragments for paper sections
6. Sanitize results (redact hostnames, paths) for public release
7. Hash final result set for reproducibility

**Deliverables**: `generated/tables/`, `generated/figures/`, `paper/fragments/`, `results/public/`

---

## Scenarios

### Security Scenarios

| ID   | Name                            | Fault                                    | Expected Gate Decision        |
|------|---------------------------------|------------------------------------------|-------------------------------|
| S0   | approved_deployment             | None (baseline)                          | APPROVED                      |
| S1   | model_weight_tampering          | Mutate model weight bytes                | DIGEST_MISMATCH               |
| S2   | tokenizer_substitution          | Replace tokenizer files/revision         | DIGEST_MISMATCH               |
| S3   | dataset_manifest_alteration     | Alter dataset manifest hash              | DIGEST_MISMATCH               |
| S4   | vulnerable_dependency           | Known CVE without VEX                    | CRITICAL_VULNERABILITY        |
| S5a  | valid_vex_not_affected          | Valid VEX justifying not_affected         | APPROVED (alert suppressed)   |
| S5b  | malformed_vex                   | Invalid VEX schema                       | VEX_MALFORMED                 |
| S5c  | unsigned_vex                    | Missing signature when required          | VEX_UNSIGNED                  |
| S5d  | wrong_component_vex             | VEX linked to incorrect component        | VEX_WRONG_COMPONENT           |
| S8   | expired_vex                     | VEX document past validity period        | VEX_EXPIRED / STALE_EVIDENCE  |
| S9a  | invalid_signature               | Corrupted cryptographic signature        | INVALID_SIGNATURE             |
| S9b  | unauthorized_signer             | Valid sig from non-allowed key           | UNAUTHORIZED_SIGNER           |
| S9c  | missing_model_digest_attestation| Attestation without model digest subject | MISSING_ATTESTATION           |
| S9d  | substituted_external_model      | Valid image, swapped mounted model       | ATTESTATION_DIGEST_MISMATCH   |
| S10  | scanner_disagreement            | Trivy/Grype report different CVEs        | Analysis-only (no gate)       |

### Availability Scenarios

| ID   | Name                   | Condition                               | Expected Behavior                     |
|------|------------------------|-----------------------------------------|---------------------------------------|
| S6a  | max_tokens_drift       | Change max_new_tokens after approval    | CONFIGURATION_DRIFT detected          |
| S6b  | timeout_drift          | Change timeout after approval           | CONFIGURATION_DRIFT detected          |
| S6c  | concurrency_drift      | Change concurrency/queue depth          | CONFIGURATION_DRIFT detected          |
| S7a  | long_output_prompts    | Prompts that maximize token generation  | Timeout enforcement, bounded latency  |
| S7b  | concurrent_burst       | N simultaneous requests                 | Queue backpressure, 503 when full     |
| S7c  | sustained_load         | Continuous load below safety cutoff     | Stable throughput, bounded P99        |
| S11  | circuit_breaker_recovery | Trigger and recover from CB activation | Service restores after cooldown       |

---

## Configurations

| ID | Name               | max_new_tokens | timeout_s | max_concurrency | queue_depth | rate_limit_rpm | circuit_breaker |
|----|--------------------|----------------|-----------|-----------------|-------------|----------------|-----------------|
| C0 | permissive_baseline| 512            | 120       | 32              | 128         | 1000           | disabled        |
| C1 | token_limit_timeout| 100            | 30        | 32              | 128         | 1000           | disabled        |
| C2 | rate_bounded       | 100            | 30        | 4               | 16          | 120            | disabled        |
| C3 | full_protection    | 100            | 30        | 4               | 16          | 120            | enabled (5/30s) |

Configurations are applied incrementally to isolate the effect of each control:
- C0 → C1: Effect of token and timeout limits
- C1 → C2: Effect of concurrency and rate limiting
- C2 → C3: Effect of circuit breaker

### Safety Limits (absolute bounds)

All configurations are further bounded by safety limits that cannot be exceeded regardless of profile:

| Parameter             | Absolute Maximum |
|-----------------------|-----------------|
| max_new_tokens        | 1024            |
| timeout_seconds       | 180             |
| max_concurrency       | 64              |
| max_queue_depth       | 256             |
| GPU memory usage      | 80%             |
| RAM usage             | 80%             |
| Test duration         | 300s (local) / 1800s (industrial) |

---

## Trial Structure

Each campaign trial follows a consistent structure:

```
Trial N:
  1. Pre-condition: verify clean workspace state
  2. Setup: prepare scenario-specific conditions
  3. Execute: run measurement (gate evaluation or load test)
  4. Record: capture all metrics and decisions
  5. Restore: return workspace to pre-trial state
  6. Validate: confirm restoration succeeded
```

### Trial Isolation

- Each trial operates on a **fresh copy** of the workspace
- Fault injection uses `FaultContext` to capture pre-state
- `restore_from_context()` reverts all mutations after measurement
- Trial results include workspace hash before and after to verify isolation

### Trial Counts

| Mode  | Trials | Requests/Trial | Warmup |
|-------|--------|----------------|--------|
| Quick | 3      | 20             | 10     |
| Full  | 30     | 200            | 10     |

Warmup requests are excluded from measurement. They ensure model caches and JIT compilation are stable before recording begins.

---

## Measurement Methodology

### Security Campaigns (RQ2, RQ3)

**Primary metric**: Detection rate (binary — gate correctly accepts/rejects)

For each scenario and trial:
- Record gate decision code
- Compare against expected decision
- Classify as True Positive, True Negative, False Positive, or False Negative

### Availability Campaigns (RQ4)

**Primary metrics**:
- Latency: P50, P95, P99 (milliseconds)
- Throughput: requests/second
- Error rate: proportion of 4xx/5xx responses
- Queue rejection rate: proportion of 503 (queue full)
- Circuit breaker activations: count and recovery time

### Overhead Campaigns

**Primary metrics**:
- BOM generation time (ms)
- Signing time (ms)
- Policy evaluation time (ms)
- Per-request digest verification overhead (μs)
- Memory overhead (MB)

---

## Statistical Analysis Approach

### Wilson Confidence Interval (Security Detection Rates)

For binary outcomes (detected/not-detected), we use the **Wilson score interval** rather than the normal approximation. Wilson intervals are preferred because:

- They are valid for small sample sizes (n=30)
- They handle extreme proportions (p near 0 or 1) correctly
- They never produce intervals outside [0, 1]

Formula:
```
p̂ = successes / n
z = z_{α/2} (1.96 for 95% CI)
center = (p̂ + z²/2n) / (1 + z²/n)
margin = (z / (1 + z²/n)) × √(p̂(1-p̂)/n + z²/4n²)
CI = [center - margin, center + margin]
```

### Block Bootstrap (Latency Percentiles)

For latency distributions, we use **non-parametric bootstrap** to construct confidence intervals around P50, P95, P99:

- 10,000 bootstrap resamples
- Percentile-based CI (not BCa, for simplicity and reproducibility)
- Fixed seed (42) for deterministic resampling
- Reports: (point estimate, lower bound, upper bound)

### Wilcoxon Signed-Rank Test (Paired Comparisons)

For comparing configurations (e.g., C0 vs C3 latency), we use the **Wilcoxon signed-rank test**:

- Non-parametric: no distributional assumptions
- Paired: compares matched trials (same prompt set, same trial index)
- Two-sided by default
- Reports: test statistic, p-value, effect size (r = Z / √N)

### Significance Level

- α = 0.05 for all hypothesis tests
- Bonferroni correction applied when comparing multiple configurations simultaneously
- 95% confidence intervals reported for all point estimates

### Reporting Standards

All results include:
1. Point estimate
2. 95% confidence interval (Wilson for proportions, bootstrap for percentiles)
3. Sample size (N trials × requests per trial)
4. Effect size where applicable
5. Raw data hash for verification

---

## Result Storage

```
results/
├── raw/                          # Unprocessed trial results (JSON)
│   ├── security-{timestamp}/
│   │   └── trial-{N}.json
│   ├── availability-{timestamp}/
│   │   └── trial-{N}.json
│   └── overhead-{timestamp}/
│       └── trial-{N}.json
├── normalized/                   # Aggregated, validated results
├── summary/                      # Statistical summaries
└── public/                       # Sanitized for publication
```

Each raw trial file contains:
```json
{
  "trial_id": "trial-001",
  "campaign_id": "security-20260722-143000-a1b2c3d4",
  "scenario": "S1",
  "configuration": "C3",
  "profile": "local",
  "timestamp": "2026-07-22T14:30:15Z",
  "duration_ms": 1234.5,
  "result": { ... },
  "workspace_hash_before": "abc123...",
  "workspace_hash_after": "abc123...",
  "environment_hash": "def456..."
}
```
