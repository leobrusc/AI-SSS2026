# Proposed Matched Overhead Experiment

**Status:** NO MATCHED CAMPAIGN EXISTS IN REPOSITORY — PROPOSAL ONLY  
**Audit determination:** INFERRED FROM CODE (no matching campaign found)

---

## Finding: No Matched Overhead Campaign Exists

A search of all campaign directories (`results/rq4/`, `results/raw/`, `generated/rq4/`) found no campaign that:
- Varies only security-control enablement (M0 vs M1) while holding all other parameters constant
- Uses the same model revision, prompt sequence, max_new_tokens, timeout, concurrency, GPU, and seed
- Produces a paired comparison of latency/throughput with vs without security controls active

The existing campaigns (`rq4-20260722-133959-e395d20d`, stress campaigns) vary configuration (C0–C3) but C0–C3 differ in token limits, rate limits, and concurrency — not just security-control enablement.

**This experiment has NOT been executed and must NOT be executed without authorization.**

---

## Proposed Design

### Objective

Isolate the latency and throughput overhead attributable exclusively to TraceAI security controls (signature verification, attestation gate, digest checking) by running paired workloads on the same hardware, model, and prompt sequence.

### Treatment Definition

| Treatment | Security controls | Description |
|-----------|------------------|-------------|
| **M0** | Disabled | Inference service running with attestation gate bypassed; no signature verification; no digest check at request time |
| **M1** | Enabled | Full deployment gate active: signature verification, attestation completeness check, digest match, signer authorization |

### Invariants (must be identical across M0 and M1)

| Parameter | Value | Source |
|-----------|-------|--------|
| Model | openai-community/gpt2 | `rq4.py:FULL_MODEL` |
| Model revision | 607a30d783dfa663caf39e06633721c8d4cfcd7e | `rq4.py:FULL_REVISION` |
| GPU | NVIDIA L4 | `config/profiles/gpu.yaml` |
| max_new_tokens | 100 | `config/profiles/gpu.yaml:inference.max_new_tokens` |
| timeout_seconds | 30 | `config/profiles/gpu.yaml:inference.timeout_seconds` |
| max_concurrency | 8 | `config/profiles/gpu.yaml:inference.max_concurrency` |
| Prompt sequence | Derived from `derive_workload_seed(campaign_id, trial_idx)` | `rq4.py:derive_workload_seed` |
| Seed | Same seed for M0 and M1 for each trial | Paired workload design |
| Trials | 30 (full campaign) | Statistical validity |
| Requests/trial | 200 | Full campaign |

### Metrics

| Category | Metrics |
|---------|---------|
| Latency | p50, p95, p99, mean, std, IQR (ms) |
| Throughput | requests/second, tokens/second |
| GPU | utilization mean/peak (%), VRAM mean/peak (MB) |
| Memory | CPU RSS (MB) |
| Rejection rate | rate-limited + queue-full rejections / total |
| Gate overhead | Time spent in attestation gate per request (requires instrumentation) |

### Hypothesis

H0: The median latency of M0 equals the median latency of M1 (no overhead from security controls).  
H1: The median latency of M1 > M0 (security controls add measurable overhead).

Statistical test: Wilcoxon signed-rank test on paired per-request latencies (matched by trial index and request index within trial).

Effect size: rank-biserial correlation r.

### Why this experiment is needed

The current RQ4 campaigns measure configurations C0–C3 which differ in multiple parameters simultaneously. It is impossible to isolate security-control overhead from token-limit, concurrency, or rate-limit effects using the existing data. A matched M0/M1 design is the only way to quantify the pure security overhead.

### Blockers

1. **GPU campaign not yet executed.** The NVIDIA L4 GPU campaign must run successfully before this experiment.
2. **M0 configuration not yet defined.** A mechanism to disable the attestation gate at inference time must be implemented (e.g., `TRACEAI_DISABLE_GATE=1` environment variable or a new profile).
3. **Gate overhead not instrumented.** The current service does not log time spent in attestation checks per request.
