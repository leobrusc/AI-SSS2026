# A100 RQ4 runbook

**RQ4_STATUS=PENDING_A100_EXECUTION**

Prerequisites: Linux x86_64, glibc 2.28+, Bash, uv, internet, exactly one NVIDIA
A100-SXM4-80GB, and a working NVIDIA driver compatible with CUDA 12.9.
Install uv using its [official instructions](https://docs.astral.sh/uv/getting-started/installation/).
Avoid competing GPU workloads. Unset CUDA_VISIBLE_DEVICES or use `0`.

```bash
git clone https://github.com/leobrusc/AI-SSS2026.git
cd AI-SSS2026
bash scripts/a100/run_all.sh
```

The tagged GitHub source ZIP/tar.gz also works: extract, enter its folder and
run the same command. No Git executable or metadata is needed.
The runner creates `.venv-a100` with uv/Python 3.11 and the committed lock,
downloads the exact tiny-GPT2 revision into ignored `.hf-cache`, verifies real
CUDA float16 parameters and runs concurrent HTTP inference.

Design: C0–C3 × 3 trials × 20 requests = 240 normal observations, plus 6 faults.
Target: torch 2.9.1+cu129, revision
`5f91d94bd9cd7190a9f3216ff93cd1dd95f2c7be`. Fault-count deviations fail validation.

Evidence directory: `results/camera_ready/a100/<campaign_id>/`. It contains
separate normal/fault CSVs, the combined native CSV, GPU telemetry, continuous
`runtime_resource_timeseries.csv`, legacy per-trial resource samples, full package
and hardware metadata, model download hashes, campaign/trial manifests, prompt
hash, configuration/service events, validation reports, console log and SHA256SUMS.
Model weights stay in the ignored cache.

Return the full paths printed after **RETURN THESE TWO FILES**:

1. `traceai_a100_results_<campaign_id>.tar.gz`
2. `traceai_a100_results_<campaign_id>.tar.gz.sha256`

Return failed diagnostic packages too: they are `NOT_VALID_FOR_PUBLICATION`.
If uv is absent, install it and retry; packaging requires Python through uv.
Keep failed packages and retry with a new campaign ID. Never edit CSVs to pass.

`bash scripts/a100/run_all.sh --dry-run` safely checks source/protocol without
GPU inference. Local checks cannot certify A100 results. Independent audit of
returned real evidence is required before RQ4 completion.
