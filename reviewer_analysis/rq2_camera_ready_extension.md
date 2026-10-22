# Camera-ready RQ2 extension
Campaign `cr-20261020T223734Z-ffdfff82`; timestamp 2026-10-20T22:37:34.380188+00:00; commit `bb2d9e4b4703b8f59dcd6ef563df374fcbe79720`; n=42.
Reproduce: `.venv/Scripts/python.exe reviewer_analysis/fresh_audit.py` (creates a NEW campaign).
Historical 240 observations remain separate and unchanged. Raw envelopes/results in `results\camera_ready\rq2_extension\cr-20261020T223734Z-ffdfff82`.
30 CR-SIG trials reach the normal ECDSA public_key.verify call once each and return INVALID_SIGNATURE.
Deterministic fixture key scalar 42 and fixed one-bit signature mutation; signature nonces are library-randomized.
Other scenarios are one diagnostic each; no population effectiveness inference.
Metadata substitution tests the separate attestation argument, not a modified signed payload. All four fields
are accepted when model_digest remains unchanged: gate does not compare supplied attestation to decoded payload.
Fresh replay and old-revision rollback accepted. Expired envelope rejected at verifier, but its timestamp is unsigned.
Removal from a nonempty allowlist rejects; an empty allowlist ACCEPTS. Not full revocation.
An attacker key with an allowlisted keyid is accepted when caller supplies its public key: fingerprint is not recomputed.
Compromised still-authorized signing key accepted. No production-key-compromise resistance established.
These are measured limitations, not silently repaired controls.
