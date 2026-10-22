# Clean-Clone Reproducibility Report

**Status:** FAILED
**Timestamp:** 2026-07-23T13:51:35.073568+00:00
**Clone directory:** `C:\Users\leolima\Documents\traceai-repro-check`

## Steps

| Step | Exit Code | Elapsed |
|------|-----------|---------|
| git_clone | 0 | 1.6s |
| git_status | 0 | N/A |
| create_venv | 0 | 26.6s |
| pip_install | -1 | 600.1s |
| pip_install_retry | 0 | 197.6s |
| phase1_rq3 | 0 | 0.5s |
| phase2_rq1 | 0 | 0.4s |
| pytest | 1 | 26.4s |

## Artifact Comparisons

| Artifact | Match | Reason |
|----------|-------|--------|
| generated/rq3/canonical_advisory_agreement.json | Yes | Semantically equivalent (timestamps excluded) |
| generated/rq1/rq1_comparison_summary.json | Yes | Semantically equivalent (timestamps excluded) |

## Nondeterministic Fields

The following fields are expected to differ between runs:
- `timestamp`, `timestamp_start`, `timestamp_end` (execution time)
- `campaign_id` (random UUID component)
- `scanner_raw_dir` (absolute path differs between machines)

These are excluded from semantic comparison.