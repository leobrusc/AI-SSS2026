# TraceAI Repository File Inventory
**Generated:** 2026-10-20  
**Auditor:** Technical Reviewer (Kiro)  
**Project root:** `C:\Users\leolima\Documents\traceai-ladc2026`

---

## Identification of Campaign Used in the Article

The article reports results from the following campaign bundle:
- **RQ1 (final):** `results/rq1/rq1-20260722-140850-18433df2` (2026-07-22T17:11)
- **RQ2 (final):** `results/raw/security-20260722-140421-f4aee0f2` (2026-07-22T17:04, 30 trials × 8 scenarios = 240)
- **RQ3 (final):** `results/rq3/rq3-20260722-140819-082e9531` (2026-07-22T17:08)
- **RQ4 (CPU diagnostic):** `results/rq4/rq4-20260722-133959-e395d20d` (2026-07-22T16:42)
- **RQ4 (stress test):** `results/rq4/rq4-stress-20260723-103231-90518de9` (2026-07-23T13:32)
- **GPU campaign:** NOT EXECUTED on this host. Validation report shows `status: FAIL` (`generated/gpu/quick_validation_report.json`).

Article claims matrix: `generated/article/claims_matrix_final.csv`

---

## File Inventory Table

| File | Type | Size (bytes) | Purpose | Relevant RQ | Notes |
|------|------|-------------|---------|------------|-------|
| **ROOT** |  |  |  |  |  |
| `model.lock.json` | JSON | 739 | Pinned model revisions | RQ1, RQ4 | revision=null; status=pending — INCOMPLETE |
| `tools.lock.json` | JSON | 1107 | Pinned tool versions | RQ3 | version=null; status=pending — INCOMPLETE |
| `pyproject.toml` | TOML | 2196 | Python project metadata | ALL | — |
| `requirements.lock` | TXT | 1634 | Pinned dependencies | RQ1 | Used for Trivy probe |
| `requirements-exact.txt` | TXT | 292 | Exact pinned deps | RQ1, RQ3 | Used as scan target |
| `requirements.in` | TXT | 436 | Unpinned deps | — | — |
| `requirements-dev.in` | TXT | 245 | Dev deps | — | — |
| `requirements.txt` | TXT | 360 | General requirements | — | — |
| `tasks.ps1` | PS1 | 10385 | Main task runner | ALL | — |
| `Makefile` | Makefile | 2247 | Build targets | ALL | — |
| `CITATION.cff` | YAML | 773 | Citation metadata | — | — |
| `.env.example` | — | 452 | Env var template | — | No secrets |
| **CONFIG/** |  |  |  |  |  |
| `config/experiment.yaml` | YAML | 4361 | Experiment parameters, C0–C3, scenarios | RQ2, RQ4 | AUTHORITATIVE — 4 configs defined |
| `config/policy.yaml` | YAML | 1811 | Fail-closed policy rules | RQ2 | allowed_signers=[] populated at runtime |
| `config/logging.yaml` | YAML | 905 | Logging config | — | — |
| `config/profiles/local.yaml` | YAML | 969 | Local profile | ALL | — |
| `config/profiles/gpu.yaml` | YAML | 1824 | NVIDIA L4 GPU profile | RQ4 | model_revision=607a30d, tiny-gpt2=5f91d94 |
| `config/profiles/container.yaml` | YAML | 1049 | Container profile | — | — |
| `config/profiles/industrial.yaml` | YAML | 1515 | Industrial profile | — | Not executed |
| **SRC/TRACEAI/** |  |  |  |  |  |
| `src/traceai/bom/cyclonedx_builder.py` | Python | 5844 | CycloneDX BOM generation | RQ1 | — |
| `src/traceai/bom/ground_truth.py` | Python | 6703 | Ground-truth graph construction | RQ1 | — |
| `src/traceai/bom/bom_link.py` | Python | 3605 | BOM-Link / cross-reference | RQ1 | — |
| `src/traceai/bom/normalization.py` | Python | 4026 | BOM normalization | RQ1 | — |
| `src/traceai/bom/validators.py` | Python | 4089 | BOM schema validation | RQ1 | — |
| `src/traceai/provenance/signer.py` | Python | 5763 | ECDSA local signer (SECP256R1) | RQ2 | Ephemeral keys, not production |
| `src/traceai/provenance/verifier.py` | Python | 6813 | Signature + attestation verifier | RQ2 | Implements signer_authorized check |
| `src/traceai/provenance/attestations.py` | Python | 4855 | Attestation builder | RQ2 | — |
| `src/traceai/policy/engine.py` | Python | 8326 | Fail-closed policy engine | RQ2, RQ3 | Core gate logic |
| `src/traceai/policy/decisions.py` | Python | 5034 | Gate decision types | RQ2 | — |
| `src/traceai/vulnerability/vex.py` | Python | 6068 | VEX document parsing + application | RQ3 | — |
| `src/traceai/vulnerability/scanners.py` | Python | 6103 | Scanner integration (Trivy, Grype) | RQ3 | — |
| `src/traceai/vulnerability/normalize.py` | Python | 4180 | CVE normalization | RQ3 | — |
| `src/traceai/service/controls.py` | Python | 6839 | Rate limiter + circuit breaker | RQ4 | — |
| `src/traceai/service/app.py` | Python | 12690 | FastAPI inference app | RQ4 | — |
| `src/traceai/service/inference.py` | Python | 5616 | Model inference wrapper | RQ4 | — |
| `src/traceai/service/telemetry.py` | Python | 4490 | NVML / CPU telemetry | RQ4 | — |
| `src/traceai/service/queueing.py` | Python | 2369 | Request queueing | RQ4 | — |
| `src/traceai/campaigns/security.py` | Python | 15715 | RQ2 security campaign | RQ2 | — |
| `src/traceai/campaigns/rq1.py` | Python | 23839 | RQ1 BOM coverage campaign | RQ1 | — |
| `src/traceai/campaigns/rq1_finalizer.py` | Python | 21465 | RQ1 metrics finalization | RQ1 | — |
| `src/traceai/campaigns/rq3.py` | Python | 41631 | RQ3 scanner agreement campaign | RQ3 | Largest source file |
| `src/traceai/campaigns/rq4.py` | Python | 48109 | RQ4 availability campaign | RQ4 | Largest source file |
| `src/traceai/campaigns/vex_property.py` | Python | 6764 | VEX property-based tests (500 cases) | RQ3 | Uses random.Random, NOT Hypothesis |
| `src/traceai/campaigns/availability.py` | Python | 8619 | Availability campaign | RQ4 | — |
| `src/traceai/campaigns/overhead.py` | Python | 8296 | Overhead measurement | RQ4 | — |
| `src/traceai/analysis/statistics.py` | Python | 10503 | Statistical analysis | ALL | — |
| `src/traceai/analysis/tables.py` | Python | 5903 | LaTeX table generation | ALL | — |
| `src/traceai/analysis/figures.py` | Python | 4945 | Plot generation | ALL | — |
| `src/traceai/analysis/narrative.py` | Python | 5542 | Narrative generation | ALL | — |
| `src/traceai/analysis/sanitization.py` | Python | 4012 | Data sanitization | ALL | — |
| `src/traceai/models.py` | Python | 3500 | Data models / enums | ALL | GateDecision enum |
| `src/traceai/hashing.py` | Python | 3082 | SHA-256 hashing utilities | RQ2 | — |
| `src/traceai/audit.py` | Python | 20301 | Audit / mock detection | ALL | — |
| `src/traceai/publication.py` | Python | 16472 | Publication artifact generation | ALL | — |
| `src/traceai/environment.py` | Python | 14341 | Environment detection | ALL | — |
| `src/traceai/settings.py` | Python | 3470 | Settings / config loader | ALL | — |
| `src/traceai/cli.py` | Python | 6028 | CLI entry points | ALL | — |
| **TESTS/** |  |  |  |  |  |
| `tests/unit/test_methodology.py` | Python | 20679 | Methodology unit tests | ALL | Article-critical — typed RQ1, oracle tests |
| `tests/unit/test_policy_engine.py` | Python | 5251 | Policy engine tests | RQ2 | — |
| `tests/unit/test_vex.py` | Python | 3378 | VEX tests | RQ3 | — |
| `tests/unit/test_hashing.py` | Python | 2772 | Hashing tests | RQ2 | — |
| `tests/unit/test_bom_normalization.py` | Python | 3641 | BOM normalization tests | RQ1 | — |
| `tests/unit/test_statistics.py` | Python | 2779 | Statistics tests | ALL | — |
| `tests/unit/test_sanitization.py` | Python | 2076 | Sanitization tests | ALL | — |
| `tests/unit/test_fault_restore.py` | Python | 3492 | Fault injection/restore | RQ2, RQ4 | — |
| `tests/unit/test_rq4_gpu_campaign.py` | Python | 18846 | RQ4 GPU campaign tests | RQ4 | — |
| `tests/unit/test_phases_3_to_5.py` | Python | 15939 | Phase 3-5 tests | RQ2, RQ3 | — |
| `tests/unit/test_gpu_l4_adaptation.py` | Python | 13099 | GPU L4 adaptation tests | RQ4 | — |
| `tests/integration/test_tamper_gate.py` | Python | 3586 | Tamper gate integration | RQ2 | — |
| `tests/integration/test_runtime_drift.py` | Python | 2545 | Runtime drift integration | RQ4 | — |
| `tests/integration/test_inference_smoke.py` | Python | 2236 | Inference smoke test | RQ4 | — |
| **RESULTS/** |  |  |  |  |  |
| `results/rq1/rq1-20260722-140850-18433df2/ground_truth_graph.json` | JSON | 15726 | Ground-truth graph (31 nodes, 28 edges) | RQ1 | **ARTICLE CAMPAIGN** |
| `results/rq1/rq1-20260722-140850-18433df2/rq1_summary.json` | JSON | 1696 | RQ1 metrics (composite 0.1724 — raw campaign) | RQ1 | **ARTICLE CAMPAIGN** — finalizer produces 0.931 |
| `results/rq1/rq1-20260722-140850-18433df2/rq1_results.csv` | CSV | 240 | RQ1 coverage by domain | RQ1 | Raw values |
| `results/rq1/rq1-20260722-140850-18433df2/traceai_ml_bom.cdx.json` | JSON | 3754 | TraceAI ML-BOM | RQ1 | CycloneDX |
| `results/rq1/rq1-20260722-140850-18433df2/trivy.cdx.json` | JSON | 1013 | Trivy CycloneDX SBOM | RQ1 | Small — tool limitation |
| `results/rq1/rq1-20260722-140850-18433df2/syft.cdx.json` | JSON | 0 | Syft output (timed out) | RQ1 | EMPTY — timeout |
| `results/rq1/rq1-20260722-140850-18433df2/linked_graph.json` | JSON | 437 | Linked BOM graph | RQ1 | — |
| `results/raw/security-20260722-140421-f4aee0f2/security_results.json` | JSON | 153540 | 240 RQ2 outcomes (30 trials × 8 scenarios) | RQ2 | **ARTICLE CAMPAIGN** |
| `results/raw/security-20260722-140421-f4aee0f2/campaign_manifest.json` | JSON | 425 | Campaign metadata | RQ2 | — |
| `results/rq3/rq3-20260722-140819-082e9531/rq3_summary.json` | JSON | 937 | RQ3 summary (Trivy=54, Grype=35) | RQ3 | **ARTICLE CAMPAIGN** |
| `results/rq3/rq3-20260722-140819-082e9531/scanner_agreement.csv` | CSV | 539 | Scanner agreement by stratum | RQ3 | **ARTICLE CAMPAIGN** |
| `results/rq3/rq3-20260722-140819-082e9531/scanner_findings_normalized.csv` | CSV | 10893 | Normalized findings | RQ3 | — |
| `results/rq3/rq3-20260722-140819-082e9531/vex_decisions.csv` | CSV | 1421 | 8 VEX conformance scenarios | RQ3 | — |
| `results/rq4/rq4-20260722-133959-e395d20d/raw_requests.csv` | CSV | 38333 | RQ4 CPU raw requests (240 obs, tiny-gpt2) | RQ4 | **ARTICLE CAMPAIGN (CPU diagnostic)** |
| `results/rq4/rq4-20260722-133959-e395d20d/campaign_manifest.json` | JSON | 388 | RQ4 manifest (quick=true, trials=3) | RQ4 | 3 trials × 20 req × 4 configs = 240 |
| `results/rq4/rq4-stress-20260723-103231-90518de9/raw_requests.csv` | CSV | 11025 | Stress test with C2/C3 rejections | RQ4 | Phase3 stress — 129 obs |
| `results/cosign/cosign-20260722-130940/cosign_results.csv` | CSV | 444 | Cosign verification results | RQ2 | 6 scenarios |
| **GENERATED/** |  |  |  |  |  |
| `generated/article/claims_matrix_final.csv` | CSV | 903 | Claims status matrix | ALL | **ARTICLE CLAIMS** |
| `generated/article/results_manifest.json` | JSON | 1261 | Article results manifest | ALL | Contains 93.1% claim origin |
| `generated/rq1/final_metrics.json` | JSON | 797 | Finalizer output (composite 1.0 vs 0.931) | RQ1 | INCONSISTENCY — see rq1_summary.md |
| `generated/rq1/rq1_comparison_correction.md` | MD | 1485 | Jaccard correction note | RQ1 | Documents universe mismatch |
| `generated/rq1/rq1_comparison_summary.json` | JSON | 1347 | Phase 2 comparison (direct universe) | RQ1 | — |
| `generated/rq1/final_obom.cdx.json` | JSON | 1701 | Final OBOM | RQ1 | — |
| `generated/rq1/syft_direct.cdx.json` | JSON | 493650 | Syft full CycloneDX | RQ1 | LARGE — 108 components |
| `generated/rq3/rq3_metric_correction.md` | MD | 4640 | Canonical advisory Jaccard correction | RQ3 | Key: Jaccard=0.6481 (canonical) |
| `generated/rq3/canonical_advisory_agreement.json` | JSON | 1383 | Canonical metrics (Trivy=54, Grype=35, intersect=35) | RQ3 | **POST-PROCESSING CORRECTION** |
| `generated/rq3/canonical_alias_classes.csv` | CSV | 2888 | Alias equivalence classes | RQ3 | — |
| `generated/rq3/phase3_agreement/rq3_agreement_summary.json` | JSON | 1993 | Phase 3 agreement analysis | RQ3 | — |
| `generated/rq3/phase3_agreement/stage1_trivy_findings.json` | JSON | 13736 | Raw Trivy findings | RQ3 | — |
| `generated/rq3/phase3_agreement/stage1_grype_findings.json` | JSON | 10693 | Raw Grype findings | RQ3 | — |
| `generated/rq3/disagreement_details.csv` | CSV | 11470 | Per-CVE disagreement | RQ3 | — |
| `generated/rq3/vex_property_cases.csv` | CSV | 27379 | 500 VEX property test cases | RQ3 | random.Random NOT Hypothesis |
| `generated/rq3/vex_decision_table.json` | JSON | 1032 | VEX truth table | RQ3 | 16 entries |
| `generated/rq4/control_activation_results.json` | JSON | 3268 | Stress campaign results | RQ4 | — |
| `generated/rq4/control_state_transitions.csv` | CSV | 3380 | C2/C3 transitions | RQ4 | — |
| `generated/rq4/phase4_cpu_diagnostic/raw_observations.csv` | CSV | 8261 | CPU diagnostic raw obs | RQ4 | — |
| `generated/rq4/phase4_cpu_diagnostic/rq4_cpu_diagnostic.json` | JSON | 2478 | CPU diagnostic summary | RQ4 | — |
| `generated/gpu/quick_validation_report.json` | JSON | 1126 | GPU campaign validation | RQ4 | status=FAIL — GPU campaign NOT done |
| `generated/gpu_runbook/preflight_results.json` | JSON | 2743 | GPU preflight check | RQ4 | — |
| `generated/audit/audit_report.json` | JSON | 8598 | Audit / mock detection report | ALL | — |
| `generated/tools/tool_versions.json` | JSON | 1983 | Tool versions detected | RQ1, RQ3 | Trivy download FAILED; trivy=0.72.0 from probe |
| `generated/analysis_results.json` | JSON | 5732 | Full analysis results | ALL | C0-C3 all identical — ISSUE |
| `generated/publication_readiness.json` | JSON | 3458 | Publication readiness matrix | ALL | — |
| `generated/doctor_report.json` | JSON | 4083 | Environment check | ALL | — |
| **FIXTURES/** |  |  |  |  |  |
| `fixtures/vex/not_affected.valid.json` | JSON | 1170 | Valid VEX fixture | RQ3 | CycloneDX VEX format |
| `fixtures/vex/expired.json` | JSON | 1274 | Expired VEX fixture | RQ3 | — |
| `fixtures/vex/wrong_component.json` | JSON | 1086 | Wrong component VEX | RQ3 | — |
| `fixtures/vex/malformed.json` | JSON | 201 | Malformed VEX | RQ3 | — |
| `fixtures/datasets/manifest.json` | JSON | 942 | Dataset manifest | RQ1, RQ2 | — |
| `fixtures/approved/model_fixture.bin` | BIN | 2048 | Synthetic model fixture | RQ2 | NOT real GPT-2 weights |
| `fixtures/prompts/sustained.jsonl` | JSONL | 671 | Sustained load prompts | RQ4 | — |
| `fixtures/prompts/long_generation.jsonl` | JSONL | 742 | Long generation prompts | RQ4 | — |
| `fixtures/prompts/burst.jsonl` | JSONL | 183 | Burst prompts | RQ4 | — |
| `fixtures/prompts/smoke.jsonl` | JSONL | 212 | Smoke test prompts | — | — |
| `fixtures/vulnerable_project/vulnerable_sbom.cdx.json` | JSON | 1601 | Vulnerable SBOM fixture | RQ3 | — |
| `fixtures/trivy_python_probe/requirements.txt` | TXT | 87 | Probe requirements for Trivy | RQ1, RQ3 | — |
| **WORKSPACE/** |  |  |  |  |  |
| `workspace/keys/ephemeral.key.pem` | PEM | 241 | Ephemeral private key | RQ2 | ⚠ NOT DISPLAYED — secret file |
| `workspace/keys/ephemeral.pub.pem` | PEM | 178 | Ephemeral public key | RQ2 | — |
| `workspace/cosign_test/test.key` | PEM | 653 | Cosign test key | RQ2 | ⚠ NOT DISPLAYED — test secret |
| `workspace/cosign_test/unauth.key` | PEM | 653 | Unauthorized signer key | RQ2 | ⚠ NOT DISPLAYED — test secret |
| `workspace/traceai.log` | LOG | 15195 | Runtime log | ALL | — |
| `workspace/security_trials/` | DIR | — | Security trial outputs | RQ2 | — |
| **MANIFESTS/** |  |  |  |  |  |
| `manifests/vex/template.cdx.json` | JSON | 1230 | VEX template | RQ3 | — |
| `manifests/k3s/deployment.yaml` | YAML | 1332 | K3s deployment | Industrial | Not executed |
| `manifests/k3s/configmap.yaml` | YAML | 316 | K3s configmap | Industrial | Not executed |
| `manifests/dependency-track/README.md` | MD | 1735 | DT integration docs | Industrial | Not executed |
| **DOCS/** |  |  |  |  |  |
| `docs/THREAT_MODEL.md` | MD | 15344 | Threat model documentation | ALL | Architectural doc |
| `docs/ARCHITECTURE.md` | MD | 15273 | System architecture | ALL | — |
| `docs/EXPERIMENT_PROTOCOL.md` | MD | 13818 | Experiment protocol | ALL | — |
| `docs/REPRODUCIBILITY.md` | MD | 11794 | Reproducibility guide | ALL | — |
| `docs/GPU_CAMPAIGN_NVIDIA_L4.md` | MD | 4697 | GPU campaign runbook | RQ4 | GPU pending |
| `docs/WINDOWS_SETUP.md` | MD | 11554 | Windows setup guide | — | — |
| `docs/audit/REPOSITORY_HYGIENE_GCP_L4_V7_1.md` | MD | 5830 | Repo hygiene audit | ALL | — |
| **SCRIPTS/** |  |  |  |  |  |
| `scripts/phase1_canonical_rq3.py` | Python | 19290 | Canonical RQ3 advisory analysis | RQ3 | Post-processing correction |
| `scripts/phase2_rq1_comparison.py` | Python | 11789 | RQ1 universe comparison | RQ1 | Correction script |
| `scripts/phase3_rq3_agreement.py` | Python | 23183 | RQ3 agreement multi-stage | RQ3 | Correction script |
| `scripts/phase3_rq4_controls.py` | Python | 21698 | RQ4 controls activation | RQ4 | Stress campaign |
| `scripts/phase4_rq4_cpu_diagnostic.py` | Python | 16008 | RQ4 CPU diagnostic | RQ4 | — |
| `scripts/phase4_repro_test.py` | Python | 14055 | Reproducibility test | ALL | — |
| `scripts/phase5_gpu_runbook.py` | Python | 24831 | GPU runbook | RQ4 | — |
| `scripts/run_gpu_campaign.sh` | SH | 16583 | GPU campaign shell script | RQ4 | For Linux GPU node |
| **PAPER/** |  |  |  |  |  |
| `paper/fragments/environment_gpu.tex` | TeX | 1317 | GPU environment fragment | RQ4 | Template, GPU pending |
| `paper/templates/environment_gpu.tex.in` | TeX | 1544 | GPU environment template | RQ4 | — |
| **TOOLS (binary)** |  |  |  |  |  |
| `.tools/bin/cosign.exe` | EXE | 186998456 | cosign 2.4.1 | RQ2 | — |
| `.tools/bin/trivy.exe` | EXE | 172207104 | trivy 0.72.0 | RQ1, RQ3 | Version confirmed via probe |
| `.tools/bin/grype.exe` | EXE | 55716864 | grype 0.86.1 | RQ3 | SHA-256 verified |
| `.tools/bin/syft.exe` | EXE | 46554624 | syft 1.18.1 | RQ1 | SHA-256 verified |

---

## Classification: Article vs Non-Article Artifacts

### Used in Article (current publication evidence)
- `results/rq1/rq1-20260722-140850-18433df2/` — RQ1 campaign
- `results/raw/security-20260722-140421-f4aee0f2/` — RQ2 30-trial campaign
- `results/rq3/rq3-20260722-140819-082e9531/` — RQ3 campaign
- `results/rq4/rq4-20260722-133959-e395d20d/` — RQ4 CPU diagnostic
- `generated/rq1/final_metrics.json` + `generated/rq1/final_rq1_summary.tex` — finalized RQ1 numbers
- `generated/rq3/canonical_advisory_agreement.json` — corrected RQ3 Jaccard
- `generated/article/claims_matrix_final.csv` — article claims

### Earlier/Superseded Runs (not article evidence)
- `results/rq1/rq1-20260722-130215-e296dfdc/` — earliest RQ1, different ground-truth (28 nodes)
- `results/rq1/rq1-20260722-132200-d56fae73/` — intermediate run
- `results/rq1/rq1-20260722-132359-eaf28430/` — intermediate run
- `results/rq1/rq1-20260722-134815-57ea20a0/` — intermediate run
- `results/rq1/rq1-20260722-140519-298522a9/` — penultimate run
- `results/rq3/rq3-20260722-130445-0d9c6cb0/` — early RQ3, different counts
- `results/rq3/rq3-20260722-133343-64bba554/` — intermediate
- `results/rq3/rq3-20260722-134951-30bc0af3/` — intermediate
- `results/raw/security-20260722-114908-f56ef709/` — early security (3 trials only)
- `results/raw/security-20260722-115004-8871a7ea/` — early security
- `results/raw/security-20260722-134955-6eaabc25/` — pre-final security

### Post-Processing Corrections (non-raw, derived)
- `scripts/phase1_canonical_rq3.py` — canonical Jaccard correction
- `scripts/phase2_rq1_comparison.py` — RQ1 universe correction
- `scripts/phase3_rq3_agreement.py` — multi-stage agreement analysis
- `scripts/phase3_rq4_controls.py` — stress testing
- `generated/rq1/rq1_comparison_correction.md` — documents Jaccard correction
- `generated/rq3/rq3_metric_correction.md` — documents canonical Jaccard correction

### Planned / Not Executed
- GPU campaign (NVIDIA L4) — `generated/gpu/quick_validation_report.json` status=FAIL
- Industrial profile — not provisioned
- Harbor / K3s / Dependency-Track — not provisioned

---

## Key Inconsistencies Identified at Inventory Stage

1. **model.lock.json**: All `revision` fields are `null` / `status=pending`. The article should reference `model_revision=607a30d783dfa663caf39e06633721c8d4cfcd7e` (from `config/profiles/gpu.yaml`) and `sshleifer/tiny-gpt2@5f91d94bd9cd7190a9f3216ff93cd1dd95f2c7be` (from `generated/control_activation_results.json`), but `model.lock.json` does not capture these.

2. **tools.lock.json**: All tool version fields are `null`. Actual versions known from `generated/tools/tool_versions.json` (grype=0.86.1, syft=1.18.1, trivy download failed; trivy=0.72.0 from probe).

3. **RQ1 composite coverage discrepancy**: Raw campaign reports `composite_coverage=0.1724` (`results/rq1/rq1-20260722-140850-18433df2/rq1_results.csv`), while the finalizer (`generated/rq1/final_metrics.json`) reports `1.0`, and `results_manifest.json` reports `0.931`. These represent three different computation passes — the article uses `0.931` from the finalizer pass in `generated/rq1/final_rq1_summary.tex`.

4. **GPU campaign not completed**: `generated/gpu/quick_validation_report.json` `status=FAIL`. Article cannot claim GPU evidence.
