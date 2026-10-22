# RQ4 Summary: Runtime Overhead and Fault-Detection Capability

**Audit status:** OBSERVED FROM RAW DATA + DERIVED  
**Primary source:** `results/rq4/rq4-20260722-133959-e395d20d/` (CPU diagnostic campaign)  
**Stress test source:** `generated/rq4/control_activation_results.json` (stress campaign)  
**GPU campaign status:** FAIL (`generated/gpu/quick_validation_report.json`)

---

## 1. Campaign Identity

| Property | Value | Source |
|----------|-------|--------|
| Campaign ID | rq4-20260722-133959-e395d20d | `campaign_manifest.json` (OBSERVED) |
| Campaign type | rq4-availability | `campaign_manifest.json` (OBSERVED) |
| Profile | local | `campaign_manifest.json` (OBSERVED) |
| Model | sshleifer/tiny-gpt2 | `campaign_manifest.json` (OBSERVED) |
| Model revision | 5f91d94bd9cd7190a9f3216ff93cd1dd95f2c7be | `control_activation_results.json` (OBSERVED) |
| Quick mode | true | `campaign_manifest.json` (OBSERVED) |
| Trials | 3 | `campaign_manifest.json` (OBSERVED) |
| Requests per trial | 20 | `campaign_manifest.json` (OBSERVED) |
| **Total observations** | **240** | `campaign_manifest.json` (OBSERVED) — 3 × 4 configs × 20 = 240 |
| Inference type | REAL_HTTP | `campaign_manifest.json` (OBSERVED) |
| GPU | NOT_APPLICABLE | `campaign_manifest.json` (OBSERVED) |

---

## 2. Configuration Parameters

Source: `config/experiment.yaml` (OBSERVED)

| Config | max_new_tokens | timeout_s | concurrency | queue | rate_rpm | CB threshold | CB timeout |
|--------|---------------|-----------|-------------|-------|---------|-------------|-----------|
| C0 | 512 | 120 | 32 | 128 | 1000 | disabled | N/A |
| C1 | 100 | 30 | 32 | 128 | 1000 | disabled | N/A |
| C2 | 100 | 30 | 4 | 16 | 120 | disabled | N/A |
| C3 | 100 | 30 | 4 | 16 | 120 | 5 failures | 30s |

---

## 3. Per-Configuration Metrics (Normal Observations Only)

Source: DERIVED FROM `results/rq4/rq4-20260722-133959-e395d20d/raw_requests.csv`

Note: "normal" = all 240 requests in this campaign (campaign manifest does not flag warm-up or fault-injection separately).

| Config | N requests | N success | N rejected | Rejection rate | Latency p50 (ms) | Latency p95 (ms) | Latency mean (ms) | Latency std (ms) | Latency IQR (ms) | Tokens/req mean |
|--------|-----------|-----------|-----------|---------------|-----------------|-----------------|------------------|-----------------|-----------------|----------------|
| C0 | 60 | 60 | 0 | 0.00 | 406.5 | 481.0 | 411.0 | 37.6 | 56.5 | 50.0 |
| C1 | 60 | 42 | 18 | **0.30** | 396.7 | 451.0 | 402.5 | 30.6 | 39.5 | 20.0 |
| C2 | 60 | 38 | 22 | **0.37** | 390.4 | 471.9 | 395.3 | 47.8 | 62.2 | 20.0 |
| C3 | 60 | 58 | 2 | 0.03 | 397.3 | 456.8 | 394.0 | 29.6 | 33.4 | 20.0 |

---

## 4. GPU / Hardware Metrics

GPU utilization, VRAM usage, and GPU memory columns are **NOT AVAILABLE** for this campaign:
- `raw_requests.csv` columns `gpu_utilization_percent` and `gpu_memory_mb` are empty for all 240 rows
- This is a CPU-only campaign; no NVML telemetry was collected
- GPU metrics require the NVIDIA L4 GPU campaign, which has `status=FAIL`

CPU utilization is present in `raw_requests.csv` (column `cpu_percent`), with values observed in the range 68–83%.

---

## 5. Critical Inconsistencies in Published Analysis

### 5.1 analysis_results.json shows identical latency for C0–C3

Source: `generated/analysis_results.json`

```json
"C0": {"latency": {"p50": 257.72, "p95": 352.89}},
"C1": {"latency": {"p50": 257.72, "p95": 352.89}},
"C2": {"latency": {"p50": 257.72, "p95": 352.89}},
"C3": {"latency": {"p50": 257.72, "p95": 352.89}}
```

All four configurations show identical latency. This contradicts the raw `raw_requests.csv` data (C0: 406.5ms, C1: 396.7ms, C2: 390.4ms, C3: 397.3ms p50).

**Root cause (inferred from code):** The `analysis_results.json` was generated from an earlier campaign run that may have had different data, or the availability analysis module averaged across all configurations without per-config filtering.

**Correct values to use:** The raw `raw_requests.csv` derived values above.

### 5.2 C1 rejection rate anomaly (30%)

C1 is configured with `max_concurrency=32`, `rate_limit_rpm=1000`, and no circuit breaker. This should not produce rejections under sequential load at 20 requests/trial. Yet 18/60 requests are marked `rejected=True` in the CSV.

One trial (`C1-t2`) shows 18 rejections out of 20 requests — suggesting the rate limiter state carried over from a previous test or the configuration was applied differently for that trial.

### 5.3 Model in CPU campaign ≠ model for article

The CPU diagnostic uses `sshleifer/tiny-gpt2` (2M parameters), not `openai-community/gpt2` (124M). Latency measurements on tiny-gpt2 cannot be compared to production GPT-2.

---

## 6. Warmup / Fault Injection

The CPU diagnostic campaign (`rq4-20260722-133959-e395d20d`) does **not** have a warm-up phase or fault injection observations segregated in the manifest. All 240 observations are flagged as normal requests (`rejected=False` for successful ones; `rejected=True` for control-enforced rejections).

The stress campaign (`rq4-stress-20260723-103231-90518de9`) specifically exercises fault injection via the circuit breaker (C3: 23 timeouts + 22 circuit breaker rejections). These are NOT the 240 normal observations.

---

## 7. Trial-Level Dispersion

Source: DERIVED from `raw_requests.csv`

| Config | Trial | Latency p50 | Latency mean | Notes |
|--------|-------|------------|-------------|-------|
| C0 | t0 | 380.6 | 384.0 | — |
| C0 | t1 | 393.5 | 404.6 | — |
| C0 | t2 | 445.3 | 444.2 | Highest latency trial |
| C1 | t0 | 399.6 | 409.6 | All 20 succeed |
| C1 | t1 | 396.7 | 397.2 | All 20 succeed |
| C1 | t2 | 393.7 | 384.2 | Only 2 succeed; 18 rejected |
| C2 | t0 | N/A | N/A | All 20 rejected |
| C2 | t1 | 359.1 | 365.3 | 2 rejected |
| C2 | t2 | 418.1 | 422.4 | All 20 succeed |
| C3 | t0 | 399.3 | 401.3 | 1 rejected |
| C3 | t1 | 397.0 | 399.9 | All 20 succeed |
| C3 | t2 | 379.1 | 380.3 | 1 rejected |

**Observation:** Trial-level variability in C1 and C2 is very high (C1-t2: 18/20 rejected; C2-t0: 20/20 rejected; C2-t2: 0/20 rejected). This suggests non-stationarity in the test setup — possibly the rate limiter state was not reset between trials.

---

## 8. GPU Campaign Status

Source: `generated/gpu/quick_validation_report.json`

| Gate | Status |
|------|--------|
| `observation_count_exact_240` | PASS |
| `gpu_utilization_non_null` | PASS |
| `gpu_memory_non_null` | PASS |
| `c1_completed` | **FAIL** |
| `c2_control_activated` | **FAIL** |
| `model_revision_matches` | **FAIL** |
| `working_tree_clean` | **FAIL** |
| **Overall status** | **FAIL** |

The GPU campaign cannot be used as publication evidence. The NVIDIA L4 campaign must be re-run on a GPU node with a clean working tree and matching model revision.
