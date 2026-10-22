# Final evidence audit — STOP BEFORE MANUSCRIPT EDIT
Timestamp 2026-10-20T22:45:28.088433+00:00; commit bb2d9e4b4703b8f59dcd6ef563df374fcbe79720; primary extension campaign cr-20261020T223734Z-ffdfff82.

SAFE_TO_INCLUDE
- Historical RQ2 30×8=240, TP210 TN30 FP0 FN0, scenario stratification and exact CP95 intervals.
- S9a is SIGNATURE_AUTHENTICITY_NOT_TESTED_BY_S9A; authorized-key CR-SIG30 reaches ECDSA and rejects all mutations.
- Trivy0.72.0/Grype0.86.1 raw findings54/35; raw intersection4 union85 Jaccard.0470588;
  explicit alias canonical intersection35 union54 Jaccard.6481481; component discrepancies in CSV.
- Existing generator random.Random42: 500 cases/500 agreements/0 counterexamples; Boolean policy flag testing, not Hypothesis.
- Explicitly measured extension limitations: fresh replay, rollback, metadata substitution accepted;
  compromised still-authorized signer accepted; missing keyid/public-key binding; empty allowlist permits all;
  unauthenticated timestamp can be refreshed. No implementation changes made to conceal these outcomes.

SAFE_WITH_LIMITATION
- 42 extension observations are diagnostic properties, separate from historical240. Primary campaign cr-20261020T223734Z-ffdfff82.
  Earlier independent smoke extension cr-20261020T223724Z-60cf801f also has42; do not pool into primary42 or historical240.
  Fixed fixture key scalar42 and one-bit mutation; signatures have library-randomized nonces. No security-effectiveness generalization.
- CPU240 diagnostic and separate CPU80 diagnostic metrics; successful-only latency stats and rejection denominators explicit.
  Throughput derived from timestamp spans, not measured steady-state throughput. Stress files lack complete hardware provenance.
- GrypeDB built2026-03-09T00:31:20Z schema5 and recorded checksum; historical TrivyDB timestamp/version unavailable.
- Code dtype CPUfloat32/CUDAfloat16; no observed historic tensor dtype established. No quantization/compression setup found.
- VEX custom expiry, caller Boolean trust, first-statement conflict behavior and advisory-only suppression require explicit limitations.
- G=(V,E) formalization and stronger invariants are architectural, only source-supported subset implemented/evaluated.

UNSUPPORTED
- Current 27/29=93.1% claim: files conflict (raw5/29; stale27/29 summary; current29/29 metrics; changed universe).
  Independent raw-universe name/role audit28/29 does not repair lineage or certify artifact identity.
- NVIDIA L4 runtime/VRAM/utilization/latency/throughput claims: PAPER_PRIMARY_GPU_CAMPAIGN_NOT_FOUND.
  generated/gpu/quick_validation_report.json has campaign_id=test and is GPU_MOCK/unit output, not failed real hardware evidence.
- Matched security-control overhead, larger-model or heterogeneous-accelerator results.
- Full cryptographic cross-document binding, anti-replay/rollback resistance, production signer revocation, semantic backdoor/production-scale security.
- Native HALF_OPEN event name as proof of observed HALF_OPEN state; zero placeholder fault latencies as measurements.

NEW_EXPERIMENT_REQUIRED
- Real L4 run following NVIDIA_L4_CAMERA_READY_RUNBOOK.md with exact tiny-GPT2 revision,240 normal+6 faults and actual tensors/NVML.
- Independent fault timing/state observations and repeated-trial uncertainty if those claims are retained.
- Matched paired controls only if overhead is claimed; larger models/heterogeneous accelerators remain future work.
- Reconcile/freeze RQ1 universe and historical-to-current identity mappings; capture a separately labeled experiment if needed.
- Recover historical TrivyDB metadata if possible; a fresh scan cannot retroactively supply it.

STOP GATE
No main.tex or .bib found recursively. No manuscript was edited, backed up, compiled or certified as six pages.
Phases21–24 manuscript operations are intentionally NOT EXECUTED because major claims remain unsupported and source is absent.
No commits/pushes; no GPU execution. All356 historical files are checked by hash in final integrity report.
Focused regression suite:30 passed,1 Pydantic deprecation warning; JUnit results/camera_ready/local_checks.xml.
Tests which write generated/gpu reports were not run in original checkout; historical evidence must remain immutable.
All reviewer requests mapped individually in reviewer_response_matrix.md/CSV (97 rows).
