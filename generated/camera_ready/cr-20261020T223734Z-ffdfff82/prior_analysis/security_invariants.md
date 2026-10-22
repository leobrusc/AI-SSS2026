# Security Invariants

**Audit status:** INFERRED FROM CODE + OBSERVED FROM CAMPAIGNS  
**Sources:** `src/traceai/policy/engine.py`, `src/traceai/provenance/verifier.py`,  
`src/traceai/service/controls.py`, `results/raw/security-20260722-140421-f4aee0f2/security_results.json`

---

## INV-1: Artifact Identity Consistency

**Claim:** The SHA-256 digest of every artifact loaded at deployment time must match the digest recorded in the signed attestation.

| Property | Value |
|----------|-------|
| **Implemented** | YES |
| **Source file/function** | `src/traceai/provenance/verifier.py` → `verify_digest_match()`; `src/traceai/hashing.py` → `hash_file()` |
| **Policy check name** | `digest_match` |
| **Gate decision on failure** | `GateDecision.DIGEST_MISMATCH` |
| **Evidence from campaign** | S1 (model tampering), S2 (tokenizer), S3 (manifest), S9d (model substitution): all 30 × 4 = 120 trials → `DIGEST_MISMATCH` (OBSERVED from `security_results.json`) |
| **Tested** | YES — 4 scenarios × 30 trials |
| **Limitation** | Digest is computed over the fixture binary (`fixtures/approved/model_fixture.bin`, 2048 bytes), not real GPT-2 model weights. The mechanism is valid; the fixture is synthetic. |

---

## INV-2: Signature Authenticity

**Claim:** Every attestation must carry a valid ECDSA-P256/SHA-256 signature from an authorized signer.

| Property | Value |
|----------|-------|
| **Implemented** | PARTIALLY |
| **Source file/function** | `src/traceai/provenance/verifier.py` → `verify_signature()` |
| **Policy checks** | `signer_authorized` (checked first) → `evidence_fresh` → `cryptographic verify` |
| **Gate decisions on failure** | `GateDecision.UNAUTHORIZED_SIGNER`, `GateDecision.STALE_EVIDENCE`, `GateDecision.INVALID_SIGNATURE` |
| **Evidence from campaign** | S9a and S9b: 60 trials → `UNAUTHORIZED_SIGNER` (OBSERVED). The `signer_authorized` check fires before ECDSA verification. S0: 30 trials → `APPROVED` (OBSERVED — valid signature accepted). |
| **Tested** | Partial. Authorization check: YES (S9a, S9b). Cryptographic invalidity: NOT TESTED (no scenario presents an authorized-key with corrupted signature bytes). Freshness/stale: NOT TESTED. |
| **Limitation** | S9a is misnamed — "invalid_signature" never reaches ECDSA verification. A scenario with `keyid` in the allowlist but corrupted `sig` bytes would be required to test the cryptographic verification path. |

---

## INV-3: Cross-Document Graph Consistency

**Claim:** Component identities must be consistent across all BOM documents (ML-BOM, SBOM, HBOM, OBOM). A component present in the SBOM must resolve to the same identity as represented in the ML-BOM.

| Property | Value |
|----------|-------|
| **Implemented** | PARTIALLY |
| **Source file/function** | `src/traceai/bom/validators.py` → schema validation; `src/traceai/campaigns/rq1_finalizer.py` → coverage computation (name matching) |
| **Evidence** | The finalizer computes coverage by matching component names across domain-specific BOMs. No cross-document digest check is performed. `linked_graph.json` records BOM-to-BOM URN links but does not verify semantic consistency. |
| **Tested** | Schema validation: YES (0 failures in campaign). Cross-identity consistency: NOT TESTED. |
| **Limitation** | Coverage computation (`rq1_finalizer.py`) uses name matching, not digest or PURL matching. A component could appear in the SBOM with a different version from what appears in the ML-BOM without triggering any invariant violation. |

---

## INV-4: Policy/VEX Validity and Freshness

**Claim:** VEX documents must be schema-valid, unexpired, component-matched, and optionally signed before suppressing vulnerability alerts.

| Property | Value |
|----------|-------|
| **Implemented** | YES |
| **Source file/function** | `src/traceai/policy/engine.py` → `evaluate_vex()`; `src/traceai/vulnerability/vex.py` → `VexDocument._parse()`, `is_expired`, `validate_vex_schema()`, `check_component_linkage()` |
| **Policy checks** | `vex_schema_valid` → `vex_not_expired` → `vex_component_match` → `vex_signed_or_not_required` |
| **Gate decisions on failure** | `VEX_MALFORMED`, `VEX_EXPIRED`, `VEX_WRONG_COMPONENT`, `VEX_UNSIGNED` |
| **Evidence from campaign** | RQ3: 8 VEX conformance scenarios (V0–V7), all pass (8/8). Source: `results/rq3/rq3-20260722-140819-082e9531/vex_decisions.csv` (OBSERVED). 500 property-based tests: 0 counterexamples (OBSERVED from `generated/rq3/vex_property_cases.csv`). |
| **Tested** | YES — 8 deterministic scenarios + 500 property-based cases |
| **Limitation** | `max_vex_age_hours: 720` (30 days) in `policy.yaml`. The freshness check for VEX uses a per-document `traceai:expires` property, not a global TTL enforced at gate evaluation time. Freshness is checked in `VexDocument.is_expired` but not directly wired into `evaluate_vex()` for the general case — it relies on the `vex_expired` parameter being computed by the caller. |

---

## INV-5: Approved vs Effective Configuration Consistency

**Claim:** The runtime inference configuration (max_new_tokens, timeout, concurrency, etc.) must match the approved configuration. Any drift from the approved state must be detected and rejected.

| Property | Value |
|----------|-------|
| **Implemented** | YES |
| **Source file/function** | `src/traceai/policy/engine.py` → `check_configuration_drift()`; `src/traceai/service/controls.py` → `ControlsManager.get_configuration_dict()` |
| **Policy check** | `configuration_matches` → `GateDecision.CONFIGURATION_DRIFT` |
| **Evidence from campaign** | RQ4 stress campaign: `generated/rq4/control_activation_results.json` records configuration changes per configuration (C0–C3). The availability campaign (`rq4-20260722-133959-e395d20d`) used 4 distinct configurations but `analysis_results.json` shows all C0–C3 with identical latency metrics — suggesting the configuration drift check was not exercised across distinct conditions in the recorded metrics. |
| **Tested** | Activation: YES (C2 rate limiting, C3 circuit breaker triggered in stress campaign). Configuration drift gate: NOT DIRECTLY TESTED as a fault scenario. |
| **Limitation** | The RQ4 CPU campaign measured different configurations (C0–C3) but the `analysis_results.json` shows identical latency for all four — indicating the metrics were not correctly differentiated. The stress campaign (`rq4-stress-20260723-103231-90518de9`) does show distinct outcomes per configuration. INV-5 enforcement exists in the code but is not evaluated as a deliberate fault scenario in RQ2. |

---

## INV-6: Runtime Attribution to Model/Configuration Identity

**Claim:** Every inference request can be attributed to a specific model version and configuration state. The model identity (revision/digest) and the active configuration must be recorded in telemetry and cross-referenced against the approved attestation.

| Property | Value |
|----------|-------|
| **Implemented** | PARTIALLY |
| **Source file/function** | `src/traceai/service/telemetry.py` (records cpu_percent, rss_mb, per-request); `generated/rq4/control_activation_results.json` → `model_revision: "5f91d94bd9cd7190a9f3216ff93cd1dd95f2c7be"` |
| **Evidence** | Campaign manifest (`results/rq4/rq4-20260722-133959-e395d20d/campaign_manifest.json`) records `model_id: "sshleifer/tiny-gpt2"`. GPU campaign manifest (`generated/gpu/quick_validation_report.json`) records `model_revision_matches: false` (FAIL gate). |
| **Tested** | Model identity recording: YES (model_id in manifest). Model digest cross-check at inference time: NO — the inference service does not re-verify the loaded model's digest against the attestation before each request. The attestation gate runs at deployment time only. |
| **Limitation** | Model revision is recorded in the GPU profile (`config/profiles/gpu.yaml`: `model_revision: "607a30d783dfa663caf39e06633721c8d4cfcd7e"`) but `model.lock.json` has `revision: null`. The GPU quick validation report shows `model_revision_matches: false` — the actual loaded model revision did not match the declared revision. This is a concrete failure of INV-6 in the GPU campaign evidence. |

---

## Summary Table

| Invariant | Implemented | Tested in Campaign | Key Limitation |
|-----------|------------|-------------------|---------------|
| INV-1: Artifact digest | YES | YES (S1,S2,S3,S9d: 120 trials) | Synthetic fixtures only |
| INV-2: Signature authenticity | PARTIAL | PARTIAL (S9a/S9b: authorization; not cryptographic) | S9a does not reach ECDSA verify |
| INV-3: Cross-document consistency | PARTIAL | Schema only | No cross-digest check |
| INV-4: VEX validity/freshness | YES | YES (8 + 500 cases) | Freshness relies on caller-computed flag |
| INV-5: Config consistency | YES | PARTIAL (C2/C3 activation; not as fault scenario) | RQ2 does not inject config drift |
| INV-6: Runtime attribution | PARTIAL | PARTIAL (model_id recorded; digest not re-checked) | GPU campaign: model_revision_matches=false |
