# RQ2 Summary: 240 Artifact-Integrity Outcomes

**Audit status:** VERIFIED FROM RAW DATA  
**Primary source:** `results/raw/security-20260722-140421-f4aee0f2/security_results.json`  
**Campaign manifest:** `results/raw/security-20260722-140421-f4aee0f2/campaign_manifest.json`

---

## 1. Campaign Structure — 30 × 8 = 240

Source: `campaign_manifest.json`
- `trial_count`: 30 (OBSERVED)
- `scenario_count`: 8 (OBSERVED)
- `total_observations`: 240 (OBSERVED)
- `campaign_id`: security-20260722-140421-f4aee0f2
- `started_at`: 2026-07-22T17:04:38.297249+00:00
- `quick`: false

---

## 2. The 8 Scenarios

All 8 scenarios confirmed in raw data (`scenario_id` field):

| Scenario ID | Scenario Name | Category | n trials |
|-------------|--------------|---------|---------|
| S0 | approved_deployment | legitimate / unchanged | 30 |
| S1 | model_weight_tampering | artifact modification | 30 |
| S2 | tokenizer_substitution | tokenizer substitution | 30 |
| S3 | dataset_manifest_alteration | dataset manifest modification | 30 |
| S9a | invalid_signature | invalid signature | 30 |
| S9b | unauthorized_signer | unauthorized signer | 30 |
| S9c | missing_model_digest_attestation | missing attestation | 30 |
| S9d | substituted_external_model | model substitution | 30 |

**Total: 8 × 30 = 240 ✓**

---

## 3. Decision Outcomes per Scenario

All outcomes observed from `security_results.json`:

| Scenario | Decision (all 30 trials identical) | reason_code |
|---------|-----------------------------------|-------------|
| S0 | APPROVED | All policy checks passed |
| S1 | DIGEST_MISMATCH | Policy check failed: digest_match |
| S2 | DIGEST_MISMATCH | Policy check failed: digest_match |
| S3 | DIGEST_MISMATCH | Policy check failed: digest_match |
| S9a | UNAUTHORIZED_SIGNER | Policy check failed: signer_authorized |
| S9b | UNAUTHORIZED_SIGNER | Policy check failed: signer_authorized |
| S9c | MISSING_ATTESTATION | Policy check failed: attestation_valid |
| S9d | DIGEST_MISMATCH | Policy check failed: digest_match |

---

## 4. Confusion Matrix

**Definition:** Positive = invalid/tampered condition (any scenario except S0)

| | Predicted Positive (rejected) | Predicted Negative (accepted) |
|--|-------------------------------|-------------------------------|
| **Actual Positive (invalid)** | TP = 210 | FN = 0 |
| **Actual Negative (legitimate)** | FP = 0 | TN = 30 |

| Metric | Value | Source |
|--------|-------|--------|
| TP | 210 | OBSERVED — 7 invalid scenarios × 30 trials, all rejected |
| TN | 30 | OBSERVED — S0 × 30 trials, all APPROVED |
| FP | 0 | OBSERVED — `false_positive` flag = false for all S0 trials |
| FN | 0 | OBSERVED — `false_negative` flag = false for all invalid trials |
| **Total** | **240** | VERIFIED |

---

## 5. Derived Metrics

| Metric | Formula | Value |
|--------|---------|-------|
| TPR (sensitivity/recall) | TP/(TP+FN) = 210/210 | **1.0000** |
| TNR (specificity) | TN/(TN+FP) = 30/30 | **1.0000** |
| FPR | FP/(FP+TN) = 0/30 | **0.0000** |
| FNR | FN/(FN+TP) = 0/210 | **0.0000** |

---

## 6. Clopper-Pearson Exact Binomial 95% CI

Computed via `scipy.stats.beta.ppf` with k (successes) and n (trials):

| Rate | k | n | CP 95% CI Lower | CP 95% CI Upper |
|------|---|---|----------------|----------------|
| FPR | 0 | 30 | 0.000000 | **0.115703** |
| FNR | 0 | 210 | 0.000000 | **0.017413** |

**Interpretation:**
- With 95% confidence, the true FPR is at most 11.57% (upper bound), given that 0 false positives were observed in 30 legitimate trials.
- With 95% confidence, the true FNR is at most 1.74% (upper bound), given that 0 false negatives were observed in 210 invalid trials.
- The Wilson CI cited in the paper ([0.886, 1.0] for detection rate) corresponds to a 1-sided lower bound for overall correct detection across all 240 observations.

### Stratified by Scenario

| Scenario | n | TP/TN | FP | FN | CP 95% CI (FNR upper) |
|---------|---|-------|----|----|----------------------|
| S0 (legitimate) | 30 | TN=30 | 0 | — | FPR: [0, 0.1157] |
| S1 (artifact mod) | 30 | TP=30 | — | 0 | FNR: [0, 0.1157] |
| S2 (tokenizer sub) | 30 | TP=30 | — | 0 | FNR: [0, 0.1157] |
| S3 (dataset mod) | 30 | TP=30 | — | 0 | FNR: [0, 0.1157] |
| S9a (invalid sig) | 30 | TP=30 | — | 0 | FNR: [0, 0.1157] |
| S9b (unauth signer) | 30 | TP=30 | — | 0 | FNR: [0, 0.1157] |
| S9c (missing attest) | 30 | TP=30 | — | 0 | FNR: [0, 0.1157] |
| S9d (model sub) | 30 | TP=30 | — | 0 | FNR: [0, 0.1157] |

---

## 7. Critical Methodological Finding: S9a vs S9b

**INCONSISTENCY IDENTIFIED (methodological):**

| Scenario | Decision | reason_code |
|---------|---------|------------|
| S9a (invalid_signature) | UNAUTHORIZED_SIGNER | Policy check failed: signer_authorized |
| S9b (unauthorized_signer) | UNAUTHORIZED_SIGNER | Policy check failed: signer_authorized |

**Both S9a and S9b produce the same decision (`UNAUTHORIZED_SIGNER`) via the same policy check (`signer_authorized`).**

The `LocalVerifier.verify_signature()` function (file: `src/traceai/provenance/verifier.py`, lines ~80-95) checks **signer authorization first** (before cryptographic verification):
```python
# Check signer authorization
if self.allowed_fingerprints and key_id not in self.allowed_fingerprints:
    result.decision = GateDecision.UNAUTHORIZED_SIGNER
    result.reason = f"Signer '{signer_id}' (key {key_id[:8]}...) not in allowed list"
    return result  # ← EARLY RETURN — cryptographic check never reached

# Check evidence age
...

# Verify cryptographic signature  ← only reached if signer is authorized
public_key.verify(sig_bytes, payload, ec.ECDSA(hashes.SHA256()))
```

**Consequence:** S9a (named "invalid_signature") never actually tests whether the cryptographic signature verification fails — it fails earlier at the signer authorization check. The distinction between S9a ("signature from unauthorized key") and S9b ("different unauthorized key") is in the specific key used, not in the policy check path. Both scenarios exercise the same code path: `signer_authorized` fails → `UNAUTHORIZED_SIGNER`.

**What was not tested:** A scenario where:
1. The signer IS authorized (in the allowlist)
2. But the signature bytes are cryptographically invalid (tampered signature)
This would reach `ec.ECDSA` verification and produce `GateDecision.INVALID_SIGNATURE`.

**Reviewer response suggestion:** The paper should clarify that S9a tests "signature from key not in authorized allowlist" (an authorization failure), not a cryptographic verification failure. A separate scenario testing ECDSA verification failure would complement S9a/S9b.

---

## 8. Adversarial Scenario Mapping (against experiment.yaml)

The `config/experiment.yaml` defines 15 security scenarios (S0–S10). The campaign tested only 8:

| scenario_id | In experiment.yaml | Tested in campaign | Notes |
|-------------|-------------------|-------------------|-------|
| S0 | YES | YES | — |
| S1 | YES | YES | — |
| S2 | YES | YES | — |
| S3 | YES | YES | — |
| S4 (vulnerable_dependency) | YES | NO | — |
| S5a (valid_vex_not_affected) | YES | NO | Tested separately in RQ3/VEX |
| S5b (malformed_vex) | YES | NO | Tested in VEX conformance |
| S5c (unsigned_vex) | YES | NO | VEX scenario |
| S5d (wrong_component_vex) | YES | NO | VEX scenario |
| S8 (expired_vex) | YES | NO | VEX scenario |
| S9a | YES | YES | Renamed in YAML vs actual |
| S9b | YES | YES | — |
| S9c | YES | YES | — |
| S9d | YES | YES | — |
| S10 (scanner_disagreement) | YES | NO | Addressed in RQ3 |

VEX scenarios (S4, S5a-d, S8) and scanner disagreement (S10) are addressed in the RQ3 campaign rather than in the security (RQ2) campaign.
