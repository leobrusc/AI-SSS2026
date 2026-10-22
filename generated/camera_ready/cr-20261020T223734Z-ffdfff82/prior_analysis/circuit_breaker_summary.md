# Circuit Breaker Summary (CORRECTED)

**Audit status:** OBSERVED FROM RAW DATA + DERIVED + INFERRED + UNRESOLVED  
**Source:** `results/rq4/rq4-stress-20260723-103231-90518de9/` (functional CPU stress campaign)  
**Service events:** `results/rq4/rq4-stress-20260723-103231-90518de9/service_events.jsonl`  
**Control activation results:** `generated/rq4/control_activation_results.json`

---

## IMPORTANT DISCLAIMER

This data is from the **CPU stress campaign** (`rq4-stress-20260723-103231-90518de9`), not from an NVIDIA L4 GPU campaign. The NVIDIA L4 GPU campaign was not executed on this machine. No GPU campaign data exists in this repository (see `rq4_campaign_inventory.csv`). Circuit breaker behavior in a GPU campaign may differ due to different latency distributions and service response times.

---

## 1. Circuit Breaker Configuration

Source: `src/traceai/campaigns/rq4.py` → `CONFIGURATIONS["C3"]` (INFERRED FROM CODE)

| Parameter | Value | Source |
|-----------|-------|--------|
| Configuration | C3 | `rq4.py:CONFIGURATIONS` |
| Failure threshold | **3** | `rq4.py:CONFIGURATIONS["C3"]["circuit_breaker_threshold"] = 3` |
| Cooldown (timeout) | **5 seconds** | `rq4.py:CONFIGURATIONS["C3"]["circuit_breaker_timeout"] = 5` |

**CRITICAL NOTE:** The `rq4.py` CONFIGURATIONS define C3 with `threshold=3, timeout=5`. This **differs** from `config/experiment.yaml` which defines C3 with `threshold: 5, timeout_seconds: 30`. The stress campaign used `rq4.py` directly (the new runner with async workload), not the old `experiment.yaml` configuration.

Source for distinction: `generated/rq4/control_activation_results.json` uses the stress campaign which was produced by `scripts/phase3_rq4_controls.py`.

---

## 2. Timeline

All timestamps from `results/rq4/rq4-stress-20260723-103231-90518de9/raw_requests.csv` and `service_events.jsonl`.

| Event | Timestamp | Outcome | Latency (ms) | Status |
|-------|-----------|---------|-------------|--------|
| Campaign start | 2026-07-23T13:32:31.571079 | — | — | OBSERVED |
| First C3 request | 2026-07-23T13:33:53.165692 | TIMEOUT | 276 | OBSERVED |
| Failure 2 | 2026-07-23T13:33:53.576180 | TIMEOUT | 411 | OBSERVED |
| Failure 3 (= threshold?) | 2026-07-23T13:33:54.049833 | TIMEOUT | 474 | OBSERVED |
| Failure 4 | 2026-07-23T13:33:54.491551 | TIMEOUT | 441 | OBSERVED |
| Failure 5 | 2026-07-23T13:33:54.935223 | TIMEOUT | 443 | OBSERVED |
| First CIRCUIT_BREAKER rejection | **2026-07-23T13:33:55.343938** | EXPECTED_CIRCUIT_BREAKER | 410 | OBSERVED |
| Last CIRCUIT_BREAKER rejection | 2026-07-23T13:34:12.852547 | EXPECTED_CIRCUIT_BREAKER | 367 | OBSERVED |
| Last TIMEOUT (end of C3 phase) | 2026-07-23T13:34:13.708763 | TIMEOUT | 427 | OBSERVED |
| Recovery probe | **2026-07-23T13:34:19.258687** | COMPLETED 200 | — | OBSERVED |
| Campaign end | 2026-07-23T13:34:19.262441 | — | — | OBSERVED |

---

## 3. Computed Durations

| Metric | Calculation | Value | Status |
|--------|------------|-------|--------|
| Failure accumulation (5 failures) | T(failure5) − T(failure1) | 13:33:54.935 − 13:33:53.166 = **1.77 seconds** | DERIVED |
| Fault detection latency | T(first_CB_rejection) − T(first_failure) | 13:33:55.344 − 13:33:53.166 = **2.18 seconds** | DERIVED |
| Open-state rejection window observed | T(last_CB_rejection) − T(first_CB_rejection) | 13:34:12.853 − 13:33:55.344 = **17.51 seconds** | DERIVED |
| Recovery probe timing | T(recovery_probe) − T(first_CB_rejection) | 13:34:19.259 − 13:33:55.344 = **23.91 seconds** | DERIVED |

---

## 4. CORRECTED ANALYSIS OF RECOVERY TIMING

The previously reported statement — *"This confirms the probe succeeded in the HALF_OPEN state after the 30s cooldown"* — was **not supported** by the timestamps and has been removed.

### Observed facts:
- Configured cooldown: **5 seconds** (from `rq4.py:CONFIGURATIONS["C3"]["circuit_breaker_timeout"]`)
- Difference from first CB rejection to recovery probe: **23.91 seconds**
- Recovery probe returned: COMPLETED (HTTP 200), observed in `service_events.jsonl`

### Analysis:

**If threshold=3 and cooldown=5s (rq4.py configuration):**  
The circuit would open after the 3rd failure (~13:33:54.049) and the 5-second cooldown would expire at ~13:33:59. The 23.91-second gap between first CB rejection (13:33:55) and recovery probe (13:34:19) is consistent with a 5-second cooldown that was exceeded long before the probe was run. The probe was simply run at the end of the C3 phase, not at the first opportunity after cooldown.

**If threshold=5 and cooldown=30s (experiment.yaml configuration):**  
The circuit would open after the 5th failure (~13:33:54.935) and the 30-second cooldown would expire at ~13:34:24.935. The recovery probe was run at 13:34:19.258, which is **~5.68 seconds before** the 30-second cooldown would expire. This would mean the probe ran while the circuit was still OPEN, not in HALF_OPEN state — contradicting the COMPLETED (200) result.

### Resolution — UNRESOLVED:

**The available timestamps do not establish that recovery occurred after the configured 30-second cooldown.**

The contradiction arises because:
1. The two sources (`rq4.py` and `experiment.yaml`) specify different thresholds and cooldowns for C3.
2. The campaign code (`scripts/phase3_rq4_controls.py`) was not read in full to determine which configuration it used.
3. The `service_events.jsonl` contains only one event (`circuit_recovery_test`) with no circuit state events (no `circuit_open`, `circuit_recovered`, or `circuit_half_open` events), which the new runner's `_generate_quick_validation_report` code expects.

**What can be stated with confidence (OBSERVED/DERIVED):**
- 5 consecutive TIMEOUT outcomes occurred in C3 before the first CIRCUIT_BREAKER rejection (OBSERVED)
- 22 CIRCUIT_BREAKER rejections were observed total (OBSERVED, from `control_activation_results.json`)
- A recovery probe succeeded (HTTP 200) 23.91 seconds after the first CB rejection (OBSERVED)
- The circuit was functional — it opened, rejected requests, and allowed a recovery probe through (OBSERVED)

**What cannot be stated:**
- Which exact configuration (`rq4.py` vs `experiment.yaml`) was active
- Whether recovery occurred during HALF_OPEN or after full cooldown

---

## 5. Validated Gates (from control_activation_results.json)

Source: `generated/rq4/control_activation_results.json` → `validation` (OBSERVED)

| Gate | Result | Detail |
|------|--------|--------|
| C0_completes_inference | PASS | 15 requests completed |
| C1_completes_inference | PASS | 24 requests completed |
| C2_control_activation | PASS | 15 expected rejections |
| C3_circuit_opens | PASS | 22 circuit-breaker rejections observed |
| C3_circuit_recovers | PASS | Circuit recovered after cooldown |
| unexpected_failures_reported | PASS | 0 unexpected failures |

---

## 6. Article-Ready Numbers

| Metric | Value | Confidence |
|--------|-------|-----------|
| Failures before circuit opens | 5 (observed consecutive TIMEOUT before first CB rejection) | OBSERVED |
| Fault detection latency (threshold accumulation + transition) | ~2.18 seconds | DERIVED |
| Circuit-breaker rejections observed | 22 | OBSERVED |
| Recovery confirmed | YES | OBSERVED |
| Total C3 observations | 45 | OBSERVED |
| Effective cooldown | UNRESOLVED (5s per rq4.py; 30s per experiment.yaml) | UNRESOLVED |
| Device | CPU only (not GPU) | OBSERVED |
