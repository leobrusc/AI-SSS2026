# RQ2 Provenance Adversarial Scenarios

**Audit status:** INFERRED FROM CODE + OBSERVED FROM RAW DATA  
**Sources:** `src/traceai/campaigns/security.py`, `src/traceai/faults/injector.py`,  
`src/traceai/provenance/verifier.py`, `results/raw/security-20260722-140421-f4aee0f2/security_results.json`

---

## Classification Legend

| Status | Meaning |
|--------|---------|
| IMPLEMENTED_AND_TESTED | Code exists and is exercised in the 240-outcome campaign |
| IMPLEMENTED_NOT_TESTED | Code exists but is not wired into the campaign |
| PARTIALLY_IMPLEMENTED | Some aspects implemented, others missing |
| CONCEPTUAL_ONLY | Mentioned in docs or design, no code |
| NOT_PRESENT | No evidence of implementation or design intent |

---

## Scenario-by-Scenario Classification

### 1. Artifact Modification (model weight tampering)
**Status: IMPLEMENTED_AND_TESTED**  
**Source:** `src/traceai/faults/injector.py` → `inject_model_weight_tampering()`, `src/traceai/campaigns/security.py` → `_scenario_s1()`  
**Campaign evidence:** S1 — 30 trials, all return `DIGEST_MISMATCH` (OBSERVED from `security_results.json`)  
**Mechanism:** Random byte mutation in copied model file → SHA-256 digest changes → gate compares against attested digest → `PolicyEngine.evaluate()` check `digest_match` fails → `GateDecision.DIGEST_MISMATCH`  
**Notes:** Operates on a 2048-byte synthetic binary fixture (`fixtures/approved/model_fixture.bin`), not real GPT-2 weights.

---

### 2. Tokenizer Substitution
**Status: IMPLEMENTED_AND_TESTED**  
**Source:** `src/traceai/faults/injector.py` → `inject_tokenizer_substitution()`, `src/traceai/campaigns/security.py` → `_scenario_s2()`  
**Campaign evidence:** S2 — 30 trials, all return `DIGEST_MISMATCH` (OBSERVED)  
**Mechanism:** Null-byte injection into tokenizer JSON bytes → digest change → same digest check path as S1  
**Notes:** Uses synthetic tokenizer fixture created in `_scenario_s2()`.

---

### 3. Dataset Manifest Alteration
**Status: IMPLEMENTED_AND_TESTED**  
**Source:** `src/traceai/faults/injector.py` → `inject_dataset_manifest_alteration()`, `src/traceai/campaigns/security.py` → `_scenario_s3()`  
**Campaign evidence:** S3 — 30 trials, all return `DIGEST_MISMATCH` (OBSERVED)  
**Mechanism:** SHA-256 entry in manifest JSON replaced with fake hash → file content changes → digest mismatch  

---

### 4. Invalid Signature (S9a)
**Status: IMPLEMENTED_AND_TESTED (but with critical limitation — see below)**  
**Source:** `src/traceai/campaigns/security.py` → `_scenario_s9a()`  
**Campaign evidence:** S9a — 30 trials, all return `UNAUTHORIZED_SIGNER` (OBSERVED)

**Critical finding — S9a does NOT exercise cryptographic verification:**

In `_scenario_s9a()`, the envelope is constructed with `keyid="invalid"` (a literal string, not a real key fingerprint). The `LocalVerifier.verify_signature()` in `src/traceai/provenance/verifier.py` evaluates checks in this order:

1. Check signer authorization: `if key_id not in self.allowed_fingerprints` → **TRUE** (because `"invalid"` is not in the allowed list) → returns `UNAUTHORIZED_SIGNER` immediately.
2. Check evidence age: **NEVER REACHED**
3. Verify cryptographic signature (`ec.ECDSA`): **NEVER REACHED**

The scenario is named "invalid_signature" but its detection path is identical to S9b ("unauthorized_signer"). The cryptographic invalidity of the signature bytes (`"deadbeef"*16`) is never verified because the key authorization check fires first.

**What would constitute a true "invalid_signature" test:** A scenario where the signer's key IS in the allowed fingerprint list, but the signature bytes have been tampered. This would reach `public_key.verify(sig_bytes, payload, ec.ECDSA(hashes.SHA256()))` and produce `GateDecision.INVALID_SIGNATURE`.

---

### 5. Unauthorized Signer (S9b)
**Status: IMPLEMENTED_AND_TESTED**  
**Source:** `src/traceai/campaigns/security.py` → `_scenario_s9b()`  
**Campaign evidence:** S9b — 30 trials, all return `UNAUTHORIZED_SIGNER` (OBSERVED)  
**Mechanism:** A fresh `LocalSigner` is created with a different key pair in a temporary directory. The key fingerprint is not in the gate's `allowed_fingerprints` list. The verifier returns `UNAUTHORIZED_SIGNER` at the signer authorization check.  
**Notes:** S9b is the semantically correct scenario for the detection path exercised. S9a tests a degenerate form of the same path.

---

### 6. Missing Attestation (S9c)
**Status: IMPLEMENTED_AND_TESTED**  
**Source:** `src/traceai/campaigns/security.py` → `_scenario_s9c()`  
**Campaign evidence:** S9c — 30 trials, all return `MISSING_ATTESTATION` (OBSERVED)  
**Mechanism:** `create_attestation()` called with `model_digest=""` → `LocalVerifier.verify_attestation_completeness()` checks `traceai_data.get("model_digest")` → empty string is falsy → `MISSING_ATTESTATION`

---

### 7. Model Substitution (S9d)
**Status: IMPLEMENTED_AND_TESTED**  
**Source:** `src/traceai/campaigns/security.py` → `_scenario_s9d()`  
**Campaign evidence:** S9d — 30 trials, all return `DIGEST_MISMATCH` (OBSERVED)  
**Mechanism:** Attests original artifact digest, then presents a different binary file → digest mismatch

---

### 8. Rollback Attack
**Status: NOT_PRESENT**  
**Evidence:** No scenario, function, or fixture in the codebase targets rollback. A rollback attack would involve presenting an older, previously valid attestation for a component that has since been updated. The verifier checks `max_evidence_age_hours=24` (via `STALE_EVIDENCE` decision), but this is a freshness check, not a rollback-specific version-ordering check.  
**Gap:** No `revision` or `sequence_number` field in attestations is checked against a known-latest revision.

---

### 9. Replay Attack
**Status: PARTIALLY_IMPLEMENTED**  
**Evidence:** `LocalVerifier.verify_signature()` checks signature timestamp against `max_evidence_age_hours=24` (source: `config/policy.yaml`). If a previous valid attestation is replayed after 24 hours, it would be rejected as `STALE_EVIDENCE`. However, within the 24-hour window, a replay of a valid attestation would be accepted (no nonce or one-time-use token).  
**Not tested:** No campaign scenario specifically tests replay within the validity window.

---

### 10. Metadata Substitution
**Status: PARTIALLY_IMPLEMENTED**  
**Evidence:** S3 (`inject_dataset_manifest_alteration`) modifies manifest content. This changes the file digest and triggers `DIGEST_MISMATCH`. However, metadata substitution in the BOM itself (i.e., replacing BOM node metadata without changing the file digest) is not tested. The OBOM's `runtime-snapshot` node captures observed metadata but is not cross-validated against the approved BOM at runtime.  
**Not tested:** No scenario presents a BOM with substituted metadata (e.g., changed PURL or component name) without changing file content.

---

### 11. Stale Evidence
**Status: PARTIALLY_IMPLEMENTED**  
**Evidence:** `LocalVerifier.verify_signature()` → evidence age check:
```python
age = datetime.now(timezone.utc) - sig_time
if age > timedelta(hours=self.max_evidence_age_hours):
    result.decision = GateDecision.STALE_EVIDENCE
```
Source: `src/traceai/provenance/verifier.py`, lines ~98-107.  
`max_evidence_age_hours=24` from `config/policy.yaml`.  
**Not tested in campaign:** No campaign scenario advances time to trigger `STALE_EVIDENCE`. The VEX expiry test (`V4` in RQ3) tests expiry semantics for VEX documents specifically.  
**Fixture:** `fixtures/vex/expired.json` exists for VEX expiry but there is no equivalent fixture for signature evidence expiry.

---

### 12. Mismatched Revision
**Status: CONCEPTUAL_ONLY**  
**Evidence:** The `model.lock.json` file was designed to pin model revisions (`revision` field) but all entries are `null` / `status=pending`. The `config/profiles/gpu.yaml` specifies `model_revision: "607a30d783dfa663caf39e06633721c8d4cfcd7e"` but this is a configuration value, not an enforced gate check. No gate decision type or verifier method checks whether the BOM's model revision matches the artifact revision.  
**Gap:** Revision mismatch (model_revision in BOM ≠ actual loaded model revision) is not enforced as a gate check.

---

### 13. Revoked Key
**Status: NOT_PRESENT**  
**Evidence:** The policy engine and verifier have no CRL (Certificate Revocation List), OCSP (Online Certificate Status Protocol), or revocation registry. The `allowed_fingerprints` list is static and set at gate initialization (source: `src/traceai/campaigns/security.py` line `gate = create_deployment_gate(allowed_fingerprints=[signer.get_fingerprint()])`). There is no mechanism to remove a fingerprint from the list during runtime (only `update_configuration()` in `ControlsManager` handles runtime config, not key management).  
**Gap:** Key revocation requires either a revocation registry lookup or a dynamic allowlist update mechanism.

---

### 14. Expired Evidence (Signature)
**Status: IMPLEMENTED_NOT_TESTED**  
**Evidence:** `GateDecision.STALE_EVIDENCE` is defined in `src/traceai/models.py` and `LocalVerifier` checks for it (see §11 above). The policy engine also includes `("evidence_fresh", evidence_fresh, GateDecision.STALE_EVIDENCE)` in its check list. However, no campaign scenario exercises this path.

---

### 15. Compromised Signing Key Simulation
**Status: PARTIALLY_IMPLEMENTED — NOT same as S9a**  
**Evidence:** S9b (`_scenario_s9b`) simulates a compromised key scenario in the sense that an attacker has a valid signing capability but their key is not authorized. This represents post-compromise detection at the authorization layer.  
**What is missing:** A scenario where:
1. An authorized key is used to sign a modified artifact (insider threat)
2. The key is later removed from the allowlist
3. Previous attestations signed with that key are re-evaluated

This represents the temporal aspect of key compromise (revocation) which is NOT_PRESENT (see §13 above).

---

## Summary Table

| Scenario | Status | Campaign Evidence | Key Source File |
|---------|--------|-------------------|----------------|
| Artifact modification | IMPLEMENTED_AND_TESTED | S1: 30/30 DIGEST_MISMATCH | faults/injector.py:inject_model_weight_tampering |
| Tokenizer substitution | IMPLEMENTED_AND_TESTED | S2: 30/30 DIGEST_MISMATCH | faults/injector.py:inject_tokenizer_substitution |
| Dataset manifest modification | IMPLEMENTED_AND_TESTED | S3: 30/30 DIGEST_MISMATCH | faults/injector.py:inject_dataset_manifest_alteration |
| Invalid signature (crypto) | IMPLEMENTED_NOT_TESTED | S9a hits UNAUTHORIZED_SIGNER, not INVALID_SIGNATURE | campaigns/security.py:_scenario_s9a |
| Unauthorized signer | IMPLEMENTED_AND_TESTED | S9b: 30/30 UNAUTHORIZED_SIGNER | campaigns/security.py:_scenario_s9b |
| Missing attestation | IMPLEMENTED_AND_TESTED | S9c: 30/30 MISSING_ATTESTATION | provenance/verifier.py:verify_attestation_completeness |
| Model substitution | IMPLEMENTED_AND_TESTED | S9d: 30/30 DIGEST_MISMATCH | campaigns/security.py:_scenario_s9d |
| Rollback | NOT_PRESENT | Not in campaign | — |
| Replay (outside window) | PARTIALLY_IMPLEMENTED | Not tested | provenance/verifier.py (age check) |
| Metadata substitution | PARTIALLY_IMPLEMENTED | S3 covers manifest; BOM metadata not covered | — |
| Stale evidence | IMPLEMENTED_NOT_TESTED | STALE_EVIDENCE decision exists but not triggered | provenance/verifier.py |
| Mismatched revision | CONCEPTUAL_ONLY | model.lock.json has null revisions | — |
| Revoked key | NOT_PRESENT | No CRL/OCSP/revocation registry | — |
| Expired evidence (signature) | IMPLEMENTED_NOT_TESTED | STALE_EVIDENCE reachable but not exercised | provenance/verifier.py |
| Compromised signing key | PARTIALLY_IMPLEMENTED | S9b covers authorization aspect; no temporal revocation | campaigns/security.py:_scenario_s9b |
