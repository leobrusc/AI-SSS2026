# Implemented trust model and measured limitations
Source: src/traceai/provenance/{signer,verifier,attestations}.py and policy/decisions.py.

Property | Status | Evidence
---|---|---
ECDSA P-256 / SHA-256 | IMPLEMENTED | SECP256R1; ECDSA(hashes.SHA256())
SHA-256 public-key fingerprint | IMPLEMENTED | DER SubjectPublicKeyInfo hash truncated to 32 hex characters (128 bits)
Key generation | IMPLEMENTED | ec.generate_private_key; local persisted key reused unless force_new
Key persistence | IMPLEMENTED | workspace/keys/ephemeral.key.pem, unencrypted PKCS8; public SPKI PEM
Authorized signer set | PARTIAL | compares caller-provided keyid string; does not recompute public-key fingerprint; empty list allows all
Freshness | PARTIAL | optional unsigned envelope timestamp; missing/malformed timestamp bypasses expiry
Rotation | ASSUMED | operator must distribute new public key and nonempty allowlist; no lifecycle service
Allowlist removal | IMPLEMENTED WITH LIMITATION | measured removal from nonempty list rejects; removal of last key to empty list accepts
Full revocation / CRL / OCSP / PKI | NOT_IMPLEMENTED | no certificate-chain/revocation verification in LocalVerifier
KMS/HSM | NOT_IMPLEMENTED | local software keys only

Trust anchors are operator-provided public-key material and authorization configuration, assumed authentic and protected.
The verifier does not establish the binding between those two inputs itself. The trusted computing base includes
host, Python process, artifact access, policy configuration and evidence producer. Descriptive BOM records are not active controls.
Compromised but still-authorized signing key can sign malicious evidence that verifies: measured in camera-ready extension.
No identity-of-builder, semantic backdoor, hostile runtime, compromised-host, or tail-latency guarantee follows.
The separately supplied attestation is not compared to decoded signed payload; metadata substitution was accepted.
Unsigned timestamp modification can refresh old evidence. No anti-replay store or monotonic revision registry exists.
These limitations are not repaired by the audit. Historical real signature-verification outcomes are fixture tests, not production trust assurance.
