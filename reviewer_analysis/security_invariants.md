# Deployment-gate invariants
YES/PARTIAL/NO refers to implemented enforcement at the named boundary, not architecture intent.

Invariant | Enforcement | Implemented | Tested | Source function | Experiment | Failure behavior and limits
---|---|---|---|---|---|---
INV-1 artifact identity | PARTIAL | digest equality | YES | DeploymentGate.evaluate_deployment | S1/S2/S3/S9d; CR-META | bytes rejected on expected-digest mismatch; subject name/model id not bound
INV-2 signature authenticity | YES | P-256 SHA256 payload verification | YES | LocalVerifier.verify_signature | 30 CR-SIG | INVALID_SIGNATURE; caller public key assumed trusted; payload type not signed
INV-3 signer authorization | PARTIAL | nonempty keyid allowlist | YES | LocalVerifier.verify_signature | S9a/S9b; CR-ALLOWLIST-REMOVAL; CR-KEYID-BINDING | UNAUTHORIZED_SIGNER; empty set permits all; supplied key not bound to keyid
INV-4 evidence completeness | PARTIAL | nonempty subject and model_digest | YES | verify_attestation_completeness | S9c | MISSING_ATTESTATION; not full predicate/schema validation
INV-5 freshness | PARTIAL | age of envelope timestamp | YES | verify_signature | CR-REPLAY-EXPIRED; CR-UNSIGNED-TIMESTAMP-REFRESH | STALE_EVIDENCE at verifier; gate collapses to INVALID_SIGNATURE; unsigned/missing timestamp bypass
INV-6 cross-document consistency | PARTIAL | model_digest equals supplied observed value | YES | evaluate_deployment | CR-META | ATTESTATION_DIGEST_MISMATCH; independent attestation not tied to signed payload; not universal graph validation
INV-7 VEX applicability | PARTIAL | supplied schema/expiry/component/signature flags | YES | PolicyEngine.evaluate_vex | randomized 500; test_vex | first failed flag denies; suppression function matches vulnerability ID without component check
INV-8 approved/effective configuration | PARTIAL | optional digest comparison | YES | check_configuration_drift; evaluate_deployment | test_policy_engine | CONFIGURATION_DRIFT if both digests supplied; no automatic gate revalidation on runtime update
INV-9 runtime attribution | PARTIAL | request/trial/configuration identifiers | PARTIAL | rq4._send_one_async; service telemetry | historical raw CSV | associations are not signed runtime proof; prompt content not automatically gated
INV-10 rollback/revision consistency | NO | no monotonic revision rule | YES | evaluate_deployment | CR-ROLLBACK | old approved after new; ROLLBACK_RESISTANCE_NOT_ENFORCED

Proposed stronger invariants: authenticate timestamp; derive authorized public key from trusted key registry;
parse attestation solely from authenticated payload; verify all evidence links/digests; enforce current revision;
revalidate mutable AI state. These are FORMAL MODEL PROPOSED FOR PAPER, not implemented properties.
