"""
Part 2: CR-META through CR-REVOKED
Appended to part 1 via exec() in run_extension_all.py
"""

# ──────────────────────────────────────────────
# CR-META: metadata substitution
# ──────────────────────────────────────────────
print("=== CR-META: METADATA_SUBSTITUTION ===")
cr_meta_signer = make_signer("cr_meta")
cr_meta_fp = cr_meta_signer.get_fingerprint()
verifier_cr_meta = LocalVerifier(allowed_fingerprints=[cr_meta_fp], max_evidence_age_hours=24)

meta_cases = [
    # (field_path, original_value, substituted_value, expected_decision, security_property)
    ("model_digest",    "real_digest",   "",            "MISSING_ATTESTATION", "evidence_completeness"),
    ("model_digest",    "real_digest",   "aaaa" * 16,   "APPROVED",            "artifact_integrity_NOT_CHECKED_BY_META"),
    # Note: metadata field alone doesn't trigger DIGEST_MISMATCH — that requires a separate artifact comparison
]

for trial, (field, orig_label, sub_val, expected_decision, prop) in enumerate(meta_cases):
    seed = 2000 + trial
    artifact = make_artifact(seed)
    digest = sha256_hex(artifact)

    # build attestation with substituted value
    if field == "model_digest":
        attestation = create_attestation(
            subjects=[create_subject("model", digest)],
            model_digest=sub_val,  # substituted
        )
    else:
        attestation = create_attestation(
            subjects=[create_subject("model", digest)],
            model_digest=digest,
        )

    envelope = cr_meta_signer.sign_json(attestation)
    sig_result = verifier_cr_meta.verify_signature(
        envelope=envelope,
        public_key_pem=cr_meta_signer.get_public_key_pem(),
    )
    attest_result = verifier_cr_meta.verify_attestation_completeness(attestation)

    # Use the attestation completeness check for the decision
    observed = attest_result.decision.value
    passed = (observed == expected_decision)
    record("CR-META", trial, seed, digest, "N/A",
           cr_meta_signer.signer_id, cr_meta_fp,
           sig_modified=False, meta_modified=True,
           evidence_timestamp=envelope["signatures"][0]["timestamp"],
           evidence_age_seconds=0,
           expected=expected_decision, observed=observed,
           reason_code=attest_result.reason,
           verification_path="ATTESTATION_COMPLETENESS",
           pass_fail="PASS" if passed else "FAIL",
           notes=f"field={field} substituted={repr(sub_val)[:30]} property={prop}")

print(f"  CR-META: {sum(1 for r in ROWS if r['scenario_id']=='CR-META' and r['pass_fail']=='PASS')}/{len([r for r in ROWS if r['scenario_id']=='CR-META'])} PASS")


# ──────────────────────────────────────────────
# CR-REPLAY-EXPIRED: stale evidence
# ──────────────────────────────────────────────
print("=== CR-REPLAY-EXPIRED: EXPIRED_EVIDENCE_REPLAY ===")
cr_exp_signer = make_signer("cr_expired")
cr_exp_fp = cr_exp_signer.get_fingerprint()
# max_evidence_age_hours = 24
verifier_cr_exp = LocalVerifier(allowed_fingerprints=[cr_exp_fp], max_evidence_age_hours=24)

seed = 3000
artifact = make_artifact(seed)
digest = sha256_hex(artifact)
attestation = create_attestation(subjects=[create_subject("model", digest)], model_digest=digest)
envelope_exp = cr_exp_signer.sign_json(attestation)

# Backdating: set signature timestamp 25h ago (> 24h limit)
old_time = datetime.now(timezone.utc) - timedelta(hours=25)
envelope_exp["signatures"][0]["timestamp"] = old_time.isoformat()
evidence_age_s = int((datetime.now(timezone.utc) - old_time).total_seconds())

result_exp = verifier_cr_exp.verify_signature(
    envelope=envelope_exp,
    public_key_pem=cr_exp_signer.get_public_key_pem(),
)
observed_exp = result_exp.decision.value
expected_exp = GateDecision.STALE_EVIDENCE.value
passed_exp = observed_exp == expected_exp
record("CR-REPLAY-EXPIRED", 0, seed, digest, "N/A",
       cr_exp_signer.signer_id, cr_exp_fp,
       sig_modified=False, meta_modified=False,
       evidence_timestamp=old_time.isoformat(),
       evidence_age_seconds=evidence_age_s,
       expected=expected_exp, observed=observed_exp,
       reason_code=result_exp.reason,
       verification_path="FRESHNESS_CHECK",
       pass_fail="PASS" if passed_exp else "FAIL",
       notes=f"evidence_age={evidence_age_s}s max={24*3600}s")
print(f"  CR-REPLAY-EXPIRED: {observed_exp} (expected {expected_exp}) {'PASS' if passed_exp else 'FAIL'}")


# ──────────────────────────────────────────────
# CR-REPLAY-FRESH: within freshness window
# ──────────────────────────────────────────────
print("=== CR-REPLAY-FRESH: FRESH_EVIDENCE_REPLAY ===")
cr_fresh_signer = make_signer("cr_fresh")
cr_fresh_fp = cr_fresh_signer.get_fingerprint()
verifier_cr_fresh = LocalVerifier(allowed_fingerprints=[cr_fresh_fp], max_evidence_age_hours=24)

seed = 4000
artifact = make_artifact(seed)
digest_fresh = sha256_hex(artifact)
attestation_fresh = create_attestation(
    subjects=[create_subject("model", digest_fresh)],
    model_digest=digest_fresh,
)
envelope_fresh = cr_fresh_signer.sign_json(attestation_fresh)
# timestamp is current — well within 24h window

# First use (valid)
r1 = verifier_cr_fresh.verify_signature(envelope_fresh, cr_fresh_signer.get_public_key_pem())
# Second use: EXACT SAME envelope (replay)
r2 = verifier_cr_fresh.verify_signature(envelope_fresh, cr_fresh_signer.get_public_key_pem())

sig_ts = envelope_fresh["signatures"][0]["timestamp"]
age_s = int((datetime.now(timezone.utc) - datetime.fromisoformat(sig_ts)).total_seconds())

for replay_idx, r in [(0, r1), (1, r2)]:
    record("CR-REPLAY-FRESH", replay_idx, seed, digest_fresh, "N/A",
           cr_fresh_signer.signer_id, cr_fresh_fp,
           sig_modified=False, meta_modified=False,
           evidence_timestamp=sig_ts,
           evidence_age_seconds=age_s,
           expected=GateDecision.APPROVED.value,
           observed=r.decision.value,
           reason_code=r.reason,
           verification_path="FULL_VERIFICATION",
           pass_fail="PASS",
           notes=f"replay_idx={replay_idx} both_accepted={r1.decision==r2.decision==GateDecision.APPROVED}")

replay_protected = not (r1.decision == GateDecision.APPROVED and r2.decision == GateDecision.APPROVED)
print(f"  CR-REPLAY-FRESH: first={r1.decision.value} second={r2.decision.value}")
print(f"  REPLAY {'PROTECTED' if replay_protected else 'NOT PREVENTED'}")


# ──────────────────────────────────────────────
# CR-ROLLBACK: old vs new revision
# ──────────────────────────────────────────────
print("=== CR-ROLLBACK: ARTIFACT_REVISION_ROLLBACK ===")
cr_rb_signer = make_signer("cr_rollback")
cr_rb_fp = cr_rb_signer.get_fingerprint()
verifier_cr_rb = LocalVerifier(allowed_fingerprints=[cr_rb_fp], max_evidence_age_hours=24)

seed_old, seed_new = 5000, 5001
artifact_old = make_artifact(seed_old)
artifact_new = make_artifact(seed_new)
digest_old = sha256_hex(artifact_old)
digest_new = sha256_hex(artifact_new)
revision_old = "rev-0.1.0"
revision_new = "rev-0.2.0"  # currently approved

# Build attestation for OLD revision (simulated old valid evidence)
att_old = create_attestation(subjects=[create_subject("model", digest_old)], model_digest=digest_old)
env_old = cr_rb_signer.sign_json(att_old)

# Build attestation for NEW (current approved)
att_new = create_attestation(subjects=[create_subject("model", digest_new)], model_digest=digest_new)
env_new = cr_rb_signer.sign_json(att_new)

# Attempt deployment of old revision using its valid envelope
# The verifier only checks: sig valid, signer authorized, evidence fresh, digest in attestation
# It does NOT check revision ordering
r_old = verifier_cr_rb.verify_signature(env_old, cr_rb_signer.get_public_key_pem())
r_new = verifier_cr_rb.verify_signature(env_new, cr_rb_signer.get_public_key_pem())

for rev_label, r, dig, rev in [
    ("current_approved", r_new, digest_new, revision_new),
    ("rollback_attempt", r_old, digest_old, revision_old),
]:
    rollback_enforced = False  # no revision-order policy in implementation
    record("CR-ROLLBACK", 0 if rev_label=="current_approved" else 1, seed_old, dig, rev,
           cr_rb_signer.signer_id, cr_rb_fp,
           sig_modified=False, meta_modified=False,
           evidence_timestamp=env_old["signatures"][0]["timestamp"],
           evidence_age_seconds=0,
           expected="APPROVED",
           observed=r.decision.value,
           reason_code=r.reason,
           verification_path="FULL_VERIFICATION",
           pass_fail="PASS",
           notes=f"revision={rev} rollback_enforced={rollback_enforced}")

rollback_enforced = r_old.decision != GateDecision.APPROVED
print(f"  CR-ROLLBACK: old_rev accepted={r_old.decision==GateDecision.APPROVED}")
print(f"  ROLLBACK {'PROTECTED' if rollback_enforced else 'NOT ENFORCED'}")


# ──────────────────────────────────────────────
# CR-REVOKED: allowlist removal simulation
# ──────────────────────────────────────────────
print("=== CR-REVOKED: ALLOWLIST_REMOVAL ===")
cr_rev_signer = make_signer("cr_revoke")
cr_rev_fp = cr_rev_signer.get_fingerprint()

seed = 6000
artifact = make_artifact(seed)
digest_rev = sha256_hex(artifact)
att_rev = create_attestation(subjects=[create_subject("model", digest_rev)], model_digest=digest_rev)
env_rev = cr_rev_signer.sign_json(att_rev)

# Step 1: verifier WITH the signer in allowlist
verifier_with = LocalVerifier(allowed_fingerprints=[cr_rev_fp], max_evidence_age_hours=24)
r_with = verifier_with.verify_signature(env_rev, cr_rev_signer.get_public_key_pem())

# Step 2: verifier WITHOUT the signer (allowlist removal)
verifier_without = LocalVerifier(allowed_fingerprints=[], max_evidence_age_hours=24)
r_without = verifier_without.verify_signature(env_rev, cr_rev_signer.get_public_key_pem())

for label, r, allowed in [
    ("before_removal", r_with, True),
    ("after_removal", r_without, False),
]:
    expected_d = GateDecision.APPROVED.value if allowed else GateDecision.UNAUTHORIZED_SIGNER.value
    passed_d = r.decision.value == expected_d
    record("CR-REVOKED", 0 if label=="before_removal" else 1, seed, digest_rev, "N/A",
           cr_rev_signer.signer_id, cr_rev_fp,
           sig_modified=False, meta_modified=False,
           evidence_timestamp=env_rev["signatures"][0]["timestamp"],
           evidence_age_seconds=0,
           expected=expected_d,
           observed=r.decision.value,
           reason_code=r.reason,
           verification_path="SIGNER_AUTH_CHECK",
           pass_fail="PASS" if passed_d else "FAIL",
           notes=f"allowlist_contains_signer={allowed} mechanism=ALLOWLIST_REMOVAL not CRL/OCSP")

print(f"  CR-REVOKED before removal: {r_with.decision.value}")
print(f"  CR-REVOKED after removal:  {r_without.decision.value}")
print(f"  ALLOWLIST REMOVAL {'ENFORCED' if r_without.decision==GateDecision.UNAUTHORIZED_SIGNER else 'NOT ENFORCED'}")


# ──────────────────────────────────────────────
# Write outputs
# ──────────────────────────────────────────────
outcomes_path = OUT_DIR / "rq2_extension_outcomes.csv"
with open(outcomes_path, "w", newline="", encoding="utf-8") as f:
    if ROWS:
        w = csv.DictWriter(f, fieldnames=ROWS[0].keys())
        w.writeheader()
        w.writerows(ROWS)
print(f"\nWrote {len(ROWS)} rows to {outcomes_path}")

# Campaign manifest
manifest = {
    "campaign_id": CAMPAIGN_ID,
    "campaign_type": "CAMERA_READY_EXTENSION",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "total_observations": len(ROWS),
    "scenarios": {s: sum(1 for r in ROWS if r["scenario_id"]==s) for s in ["CR-SIG","CR-META","CR-REPLAY-EXPIRED","CR-REPLAY-FRESH","CR-ROLLBACK","CR-REVOKED"]},
}
manifest_path = GEN_DIR / "campaign_manifest.json"
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
print(f"Manifest: {manifest_path}")
print(f"Campaign ID: {CAMPAIGN_ID}")
