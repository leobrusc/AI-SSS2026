# Quick Validation Report — test

**Status: FAIL**
**Timestamp:** 2026-07-24T17:33:24.557947+00:00

| Gate | Result |
|------|--------|
| real_http | ✓ PASS |
| no_mock | ✓ PASS |
| observation_count_exact_240 | ✓ PASS |
| c0_completed | ✓ PASS |
| c1_completed | ✗ FAIL |
| c2_control_activated | ✗ FAIL |
| c3_opened | ✓ PASS |
| c3_open_response_observed | ✗ FAIL |
| c3_recovered | ✓ PASS |
| c3_half_open_observed | ✓ PASS |
| c3_rate_limiter_not_interfering | ✓ PASS |
| c3_initially_closed | ✓ PASS |
| gpu_timeseries_present | ✓ PASS |
| gpu_utilization_non_null | ✓ PASS |
| gpu_memory_non_null | ✓ PASS |
| resource_timeseries_present | ✓ PASS |
| service_events_nonempty | ✓ PASS |
| configuration_events_valid | ✓ PASS |
| trial_manifest_valid | ✓ PASS |
| prompt_hash_valid | ✓ PASS |
| paired_workloads | ✓ PASS |
| no_connection_error | ✓ PASS |
| no_cuda_oom | ✓ PASS |
| no_unexpected_failure | ✓ PASS |
| model_revision_matches | ✗ FAIL |
| service_profile_gpu | ✓ PASS |
| device_cuda | ✓ PASS |
| working_tree_clean | ✗ FAIL |

Observations: 240 total, 240 normal