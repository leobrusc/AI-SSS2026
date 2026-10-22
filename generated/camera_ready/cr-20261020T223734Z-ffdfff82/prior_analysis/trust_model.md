# Trust Model and Key Management

**Audit status:** INFERRED FROM CODE  
**Sources:** `src/traceai/provenance/signer.py`, `src/traceai/provenance/verifier.py`,  
`src/traceai/policy/engine.py`, `config/policy.yaml`, `workspace/keys/ephemeral.pub.pem`

---

## Legend

| Status | Meaning |
|--------|---------|
| IMPLEMENTED | Code exists and is exercised |
| IMPLEMENTED_NOT_TESTED | Code exists but campaign does not exercise this path |
| ASSUMED | Behaviour implied by architecture but not enforced in code |
| NOT_IMPLEMENTED | No code or mechanism present |

---

## 1. Cryptographic Algorithm

| Property | Value | Status | Source |
|----------|-------|--------|--------|
| Signature algorithm | ECDSA | IMPLEMENTED | `signer.py` line: `ec.ECDSA(hashes.SHA256())` |
| Elliptic curve | SECP256R1 (P-256) | IMPLEMENTED | `signer.py` line: `ec.generate_private_key(ec.SECP256R1())` |
| Hash algorithm | SHA-256 | IMPLEMENTED | `signer.py` line: `hashes.SHA256()` |
| Signature encoding | DER via Python `cryptography` lib | IMPLEMENTED | `signer.py` uses default `ec.ECDSA` signature format |
| Payload encoding | Base64-encoded canonical JSON | IMPLEMENTED | `signer_json()`: `json.dumps(data, sort_keys=True, separators=(",", ":")); base64.b64encode(...)` |
| Payload type | `application/json` | IMPLEMENTED | Envelope field `payloadType` |

---

## 2. Key Format and Storage

| Property | Value | Status | Source |
|----------|-------|--------|--------|
| Private key format | PKCS8/PEM, unencrypted | IMPLEMENTED | `signer.py`: `PrivateFormat.PKCS8, NoEncryption()` |
| Public key format | SubjectPublicKeyInfo/PEM | IMPLEMENTED | `signer.py`: `PublicFormat.SubjectPublicKeyInfo` |
| Key storage path | `workspace/keys/ephemeral.key.pem` + `ephemeral.pub.pem` | IMPLEMENTED | `signer.py`: `key_dir / "ephemeral.key.pem"` |
| Key protection | None (NoEncryption) | IMPLEMENTED (weak) | `signer.py`: `encryption_algorithm=serialization.NoEncryption()` |
| Key size | P-256 = 256-bit (equivalent ~128-bit classical security) | IMPLEMENTED | Determined by `SECP256R1()` |

---

## 3. Key Fingerprint

| Property | Value | Status | Source |
|----------|-------|--------|--------|
| Fingerprint algorithm | SHA-256 of DER-encoded public key, first 32 hex chars | IMPLEMENTED | `signer.py`: `hash_bytes(pub_bytes)[:32]` |
| Fingerprint role | Used as `keyid` in signature envelope and as allowlist identifier | IMPLEMENTED | `verifier.py`: `key_id not in self.allowed_fingerprints` |
| Fingerprint in envelope | `signatures[0].keyid` | IMPLEMENTED | `sign_json()` output |

---

## 4. Signer Identity

| Property | Value | Status | Source |
|----------|-------|--------|--------|
| Signer ID string | `"traceai-local-test"` (default) | IMPLEMENTED | `signer.py`: `signer_id: str = "traceai-local-test"` |
| Signer ID in envelope | `signatures[0].signer_id` | IMPLEMENTED | `sign_json()` output |
| Signer ID enforcement | NOT enforced — only `keyid` (fingerprint) is checked | IMPLEMENTED | `verifier.py`: checks `key_id not in self.allowed_fingerprints`, not `signer_id` |

---

## 5. Key Generation and Lifecycle

| Property | Value | Status | Source |
|----------|-------|--------|--------|
| Key generation | `ec.generate_private_key(ec.SECP256R1())` per-session if no key file exists | IMPLEMENTED | `signer.py`: `_generate_new()` |
| Key reuse across sessions | YES — loads existing key if file present | IMPLEMENTED | `signer.py`: `if not force_new and self._key_path.exists(): self._load_existing()` |
| Ephemeral (one-shot) | NO — keys persist across sessions in `workspace/keys/` | IMPLEMENTED (persistent, not ephemeral despite naming) | File timestamps confirm key reuse |
| Key rotation | No automatic rotation; `force_new=True` parameter exists but not called in campaigns | IMPLEMENTED_NOT_TESTED | `signer.py`: `initialize(force_new=False)` |
| Key expiration | NOT_IMPLEMENTED | NOT_IMPLEMENTED | No `not_after` or TTL enforced |

**Important naming inconsistency:** The class is named `LocalSigner` and documented as "ephemeral", but keys persist at `workspace/keys/ephemeral.key.pem` across sessions. The `initialize()` default (`force_new=False`) means the same key is reused for all campaign runs.

---

## 6. Allowlist and Authorization

| Property | Value | Status | Source |
|----------|-------|--------|--------|
| Allowlist type | In-memory list of fingerprint strings | IMPLEMENTED | `verifier.py`: `self.allowed_fingerprints: list[str]` |
| Allowlist population | Set at gate initialization from the active signer's fingerprint | IMPLEMENTED | `campaigns/security.py`: `create_deployment_gate(allowed_fingerprints=[signer.get_fingerprint()])` |
| Allowlist persistence | NOT_IMPLEMENTED — rebuilt each campaign run | NOT_IMPLEMENTED | No persistent keyring file |
| Policy config | `config/policy.yaml` → `allowed_signers: []` (populated at runtime) | ASSUMED | Comment in policy.yaml: "Populated at runtime from approved keyring" |
| Multi-signer support | YES — list can contain multiple fingerprints | IMPLEMENTED | `verifier.py`: `if key_id not in self.allowed_fingerprints` (list check) |

---

## 7. Evidence Freshness

| Property | Value | Status | Source |
|----------|-------|--------|--------|
| Max evidence age | 24 hours | IMPLEMENTED | `config/policy.yaml`: `max_evidence_age_hours: 24` |
| Freshness check | Compares `signatures[0].timestamp` to `datetime.now(timezone.utc)` | IMPLEMENTED | `verifier.py`: age check block |
| Freshness failure | `GateDecision.STALE_EVIDENCE` | IMPLEMENTED | `verifier.py` + `policy/engine.py` |
| Freshness tested in campaign | NO | IMPLEMENTED_NOT_TESTED | No campaign scenario triggers STALE_EVIDENCE |
| VEX freshness | Separate expiry via `fixtures/vex/expired.json`; `max_vex_age_hours: 720` (30 days) | IMPLEMENTED | `policy.yaml`, `vulnerability/vex.py` |

---

## 8. Revocation Mechanisms

| Mechanism | Status | Notes |
|-----------|--------|-------|
| Certificate Revocation List (CRL) | NOT_IMPLEMENTED | No CRL endpoint or lookup |
| OCSP (Online Certificate Status Protocol) | NOT_IMPLEMENTED | No OCSP client |
| Revocation registry | NOT_IMPLEMENTED | No external registry |
| Dynamic allowlist removal | NOT_IMPLEMENTED | `allowed_fingerprints` is immutable after gate construction |
| Key compromise detection | NOT_IMPLEMENTED | No tamper detection on key file |

---

## 9. PKI / KMS / HSM

| Component | Status | Notes |
|-----------|--------|-------|
| Public Key Infrastructure (PKI) | NOT_IMPLEMENTED | No CA, no certificate chain, no trust anchor |
| Key Management Service (KMS) | NOT_IMPLEMENTED | Keys are filesystem-only |
| Hardware Security Module (HSM) | NOT_IMPLEMENTED | No HSM integration |
| Sigstore / Fulcio | NOT_IMPLEMENTED | Comments in `signer.py` note this is "NOT Sigstore production evidence" |
| Cosign (container signing) | IMPLEMENTED for container profile | `results/cosign/` contains cosign verification results; not exercised for model artifacts in local profile |

---

## 10. Trusted Builder Assumptions

| Assumption | Status | Source |
|-----------|--------|--------|
| The signing host is trusted | ASSUMED | No attestation of the signing environment |
| The key file has not been tampered | ASSUMED | Keys stored as plaintext PEM with no HMAC or integrity check |
| The `allowed_fingerprints` list reflects genuinely authorized keys | ASSUMED | List is constructed from the active signer at campaign time |
| The attestation predicate content is accurate | ASSUMED | No independent audit of predicate values |

---

## 11. Evidence-Store Assumptions

| Assumption | Status | Source |
|-----------|--------|--------|
| Signature envelopes are stored in the campaign result files | ASSUMED | Envelopes are passed in memory; raw campaign JSON does not store envelopes |
| BOM documents represent the actual runtime environment | ASSUMED | BOM is generated programmatically; no independent verification |
| Syft and Trivy outputs are accurate | ASSUMED | Tool outputs are used as ground truth without cross-validation |

---

## 12. Security Properties Summary

### Actually Implemented (and exercised in campaigns)
- ECDSA P-256 / SHA-256 signing and verification
- Fingerprint-based signer authorization (allowlist)
- SHA-256 artifact digest attestation and checking
- Fail-closed policy evaluation (first failed check → deny)
- VEX expiry, component linkage, schema validation
- Attestation completeness checking (model_digest field)
- Rate limiting and circuit breaker (RQ4)

### Implemented but Not Evaluated in Campaigns
- Evidence freshness / STALE_EVIDENCE path
- Key rotation (`force_new=True`)
- Cross-document BOM consistency validation

### Discussed Architecturally but Not Evaluated
- Rollback / replay protection beyond 24-hour window
- Cryptographic signature verification failure (S9a design intent)
- Revision-level identity enforcement
- Key revocation

### Not Implemented
- CRL / OCSP / revocation registry
- PKI / CA / certificate chains
- KMS / HSM
- Signed key management operations
- Per-session ephemeral keys (keys persist despite "ephemeral" naming)
