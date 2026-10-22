# Fresh RQ4 audit
CPU EVIDENCE: recomputed 4 campaign/configuration rows from manifest-confirmed NOT_APPLICABLE GPU campaigns.
Latency statistics use successful status-200, nonrejected requests; np.percentile default linear interpolation.
Throughput is explicitly DERIVED from timestamp/latency spans; not a measured campaign wall-clock throughput.
Requests rejected by controls are separate from completed inference. Trial-level metrics retained.
PAPER_PRIMARY_GPU_CAMPAIGN_NOT_FOUND: generated/gpu contains a validation report, not raw L4 campaign observations.
No real L4 campaign has been established by this audit. GPU test still required.
Do not reuse prior report's config/experiment.yaml table for rq4.py campaigns: rq4.py C3 threshold=3, cooldown=5s;
config/experiment.yaml is a separate configuration source. Historical effective config requires per-campaign logs.
No parameter-matched overhead estimate established: C0 and C1 change max_new_tokens (50 vs 20 in rq4.py).

Also recomputed explicitly labeled 80-request CPU diagnostic in generated/rq4/phase4_cpu_diagnostic (20/config; one run). Stress raw CSVs without manifests remain hardware UNVERIFIED; not pooled. Older availability-20260722-115011 campaign is synthetic (_simulate_request), not CPU evidence. Existing GPU report campaign_id=test is GPU_MOCK/unit output; do not diagnose it as a failed real GPU run.

Also recomputed explicitly labeled 80-request CPU diagnostic in generated/rq4/phase4_cpu_diagnostic (20/config; one run). Stress raw CSVs without manifests remain hardware UNVERIFIED; not pooled. Older availability-20260722-115011 campaign is synthetic (_simulate_request), not CPU evidence. Existing GPU report campaign_id=test is GPU_MOCK/unit output; do not diagnose it as a failed real GPU run.
