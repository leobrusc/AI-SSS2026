# TraceAI Threat Model

## Scope

This threat model covers the **LLM inference pipeline** protected by TraceAI, from model artifact acquisition through runtime service operation. It identifies supply-chain and runtime threats that TraceAI's BOM, provenance, and gate mechanisms are designed to detect or mitigate.

**In scope**: Model artifacts, tokenizers, datasets, Python dependencies, container images, runtime configuration, inference service behavior.

**Out of scope**: Network perimeter security, user authentication/authorization to the service, prompt injection attacks on the LLM output quality, physical security.

---

## Threat Categories

### 1. Supply-Chain Threats

#### T1 — Model Weight Tampering

| Attribute    | Value |
|-------------|-------|
| **Category** | Integrity |
| **Attacker** | Insider with repo access, compromised CI pipeline, MITM on download |
| **Asset** | Model weight files (`.bin`, `.safetensors`) |
| **Impact** | Backdoored model produces attacker-controlled outputs on trigger inputs; model quality degradation |
| **Likelihood** | Medium (documented attacks: BadNets, TrojanNN, weight poisoning) |
| **Scenario** | S1 (model_weight_tampering) |

**Attack vector**: Attacker modifies one or more bytes in model weight files after the approved model has been signed. This can occur through:
- Compromised model registry (Harbor, HuggingFace Hub)
- Man-in-the-middle during model download
- Insider modifying files on shared storage
- Malicious CI job replacing model after approval

#### T2 — Tokenizer Substitution

| Attribute    | Value |
|-------------|-------|
| **Category** | Integrity |
| **Attacker** | Insider, compromised dependency, supply-chain injection |
| **Asset** | Tokenizer vocabulary, merges file, tokenizer configuration |
| **Impact** | Altered tokenization changes model behavior; can enable evasion of safety filters; denial of service via vocabulary explosion |
| **Likelihood** | Medium |
| **Scenario** | S2 (tokenizer_substitution) |

**Attack vector**: Attacker replaces tokenizer files with a modified version that:
- Maps certain inputs to different token sequences (bypassing content filters)
- Introduces vocabulary entries that trigger model misbehavior
- Uses a different revision than the approved one

#### T3 — Dataset Manifest Alteration

| Attribute    | Value |
|-------------|-------|
| **Category** | Integrity / Provenance |
| **Attacker** | Insider, compromised data pipeline |
| **Asset** | Dataset manifest (hash, source, version metadata) |
| **Impact** | Training provenance becomes unverifiable; can mask data poisoning |
| **Likelihood** | Low-Medium |
| **Scenario** | S3 (dataset_manifest_alteration) |

**Attack vector**: Attacker modifies the dataset manifest to:
- Point to a poisoned dataset while claiming the approved one
- Remove evidence of data lineage
- Mask unauthorized data sources

#### T4 — Dependency Vulnerability Introduction

| Attribute    | Value |
|-------------|-------|
| **Category** | Integrity / Availability |
| **Attacker** | Upstream maintainer compromise, typosquatting, dependency confusion |
| **Asset** | Python packages (torch, transformers, tokenizers, etc.) |
| **Impact** | Remote code execution, data exfiltration, denial of service |
| **Likelihood** | High (frequent real-world occurrences) |
| **Scenario** | S4 (vulnerable_dependency) |

**Attack vector**:
- Known CVE in a pinned dependency (detected by scanner)
- Malicious package published under a similar name (typosquatting)
- Internal package name collision with public PyPI (dependency confusion)
- Compromised maintainer account pushing backdoored release

#### T5 — VEX Document Manipulation

| Attribute    | Value |
|-------------|-------|
| **Category** | Integrity / Policy Evasion |
| **Attacker** | Insider attempting to suppress legitimate vulnerability alerts |
| **Asset** | CycloneDX VEX documents |
| **Impact** | Genuine vulnerabilities marked as not-affected; alerts suppressed without justification |
| **Likelihood** | Medium |
| **Scenarios** | S5a–S5d, S8 |

**Attack vectors**:
- Forge a VEX document claiming not_affected without valid justification (S5b: malformed)
- Submit unsigned VEX when policy requires signature (S5c)
- Link VEX to wrong component to bypass validation (S5d)
- Use an expired VEX to claim stale operational evidence is still valid (S8)

#### T6 — Signature and Attestation Forgery

| Attribute    | Value |
|-------------|-------|
| **Category** | Authenticity |
| **Attacker** | Sophisticated attacker with access to alternative signing keys |
| **Asset** | Cosign signatures, in-toto attestations |
| **Impact** | Tampered artifacts pass gate verification |
| **Likelihood** | Low (requires key compromise or policy misconfiguration) |
| **Scenarios** | S9a–S9d |

**Attack vectors**:
- Corrupt signature bytes to test verification robustness (S9a)
- Sign with a valid but unauthorized key (S9b)
- Create attestation missing required subjects like model digest (S9c)
- Use a valid container image signature but mount a different model at runtime (S9d)

---

### 2. Runtime Threats

#### T7 — Configuration Drift

| Attribute    | Value |
|-------------|-------|
| **Category** | Availability / Safety |
| **Attacker** | Misconfiguration, insider, compromised orchestrator |
| **Asset** | Service runtime configuration (tokens, timeout, concurrency) |
| **Impact** | Removal of safety controls; resource exhaustion; denial of service to other tenants |
| **Likelihood** | High (configuration drift is common in production) |
| **Scenarios** | S6a–S6c |

**Attack vectors**:
- Modify `max_new_tokens` to allow unbounded generation (S6a)
- Increase `timeout_seconds` to tie up workers indefinitely (S6b)
- Raise `max_concurrency` or `queue_depth` beyond resource capacity (S6c)
- Hot-reload configuration without gate re-evaluation

**Impact chain**: Configuration drift → safety limits removed → resource exhaustion → service unavailability

#### T8 — Resource Exhaustion

| Attribute    | Value |
|-------------|-------|
| **Category** | Availability |
| **Attacker** | External user, automated bot, misconfigured client |
| **Asset** | GPU memory, CPU, request queue, network bandwidth |
| **Impact** | Service degradation or complete unavailability |
| **Likelihood** | High |
| **Scenarios** | S7a–S7c |

**Attack vectors**:
- Submit prompts designed to maximize token generation (S7a): exhausts GPU time
- Send concurrent burst exceeding queue capacity (S7b): triggers backpressure
- Sustained high-rate traffic below individual request limits (S7c): gradual resource depletion

#### T9 — Circuit Breaker Bypass

| Attribute    | Value |
|-------------|-------|
| **Category** | Availability / Safety |
| **Attacker** | Sophisticated client, timing attack |
| **Asset** | Circuit breaker state machine |
| **Impact** | Continued operation under fault conditions; cascading failures |
| **Likelihood** | Low |
| **Scenario** | S11 (circuit_breaker_recovery) |

**Attack vectors**:
- Time requests to arrive exactly when circuit transitions from open to half-open
- Exploit race conditions in concurrent circuit breaker state updates
- Disable circuit breaker via configuration drift (covered by T7)

---

## Mitigations via BOM + Provenance + Gates

### M1 — CycloneDX AI/ML BOM

| Threat Mitigated | Mechanism |
|-----------------|-----------|
| T1, T2, T3 | BOM records exact hashes of all model files, tokenizer files, and dataset manifests. Any modification changes the computed digest. |
| T4 | BOM enumerates all dependencies with exact versions and PURLs, enabling vulnerability scanner correlation. |
| T5 | BOM provides the ground-truth component inventory against which VEX documents are validated. |

**Properties**:
- Deterministic generation (same inputs → same BOM)
- SHA-256 hash of the BOM itself is attested
- BOM completeness measured against ground truth (RQ1)
- CycloneDX 1.6 schema validation ensures structural correctness

### M2 — Cryptographic Provenance (Signing + Attestation)

| Threat Mitigated | Mechanism |
|-----------------|-----------|
| T1, T2, T3 | Signed attestation binds model digest, tokenizer digest, and dataset digest to a specific approval event. Post-approval modification invalidates the signature. |
| T6 | Signature verification against an allowed-signer keyring rejects unknown keys. Attestation schema validation rejects incomplete attestations. |
| T7 | Configuration digest is signed at approval time. Runtime drift changes the digest, which fails verification. |

**Properties**:
- Local-ephemeral keys for development (fast, no external dependency)
- Cosign-keyless for production (Fulcio + Rekor transparency log)
- Evidence freshness enforced (max_evidence_age_hours)
- Allowed-signer list is explicit (no implicit trust)

### M3 — Deployment Gate (Policy Engine)

| Threat Mitigated | Mechanism |
|-----------------|-----------|
| All threats | Gate operates in **fail-closed** mode: any missing evidence, failed verification, or policy violation results in denial. |
| T1–T3 | Digest comparison gates: DIGEST_MISMATCH on any artifact change |
| T4 | Vulnerability threshold gates: max_critical_unfixed=0, max_high_unfixed=3 |
| T5 | VEX validation gates: schema check, signature check, component-link check, expiry check |
| T6 | Signature gates: validity check, signer authorization check, attestation completeness check |
| T7 | Configuration drift gate: compares runtime digest against approved digest |
| T8 | Runtime controls: token limits, timeouts, concurrency caps, queue bounds, rate limiting |
| T9 | Circuit breaker: opens after threshold failures, enforces cooldown period |

**Gate Decision Codes**:
```
APPROVED                    → Allow deployment/request
MISSING_ARTIFACT            → Deny: required artifact not found
DIGEST_MISMATCH             → Deny: artifact hash changed
INVALID_SIGNATURE           → Deny: signature verification failed
UNAUTHORIZED_SIGNER         → Deny: signer not in allowed list
MISSING_ATTESTATION         → Deny: required attestation field missing
ATTESTATION_DIGEST_MISMATCH → Deny: attestation subject doesn't match
STALE_EVIDENCE              → Deny: evidence older than allowed
VEX_MALFORMED               → Deny: VEX schema validation failed
VEX_EXPIRED                 → Deny: VEX past validity period
VEX_WRONG_COMPONENT         → Deny: VEX targets wrong component
VEX_UNSIGNED                → Deny: VEX missing required signature
CRITICAL_VULNERABILITY      → Deny: unmitigated critical CVE
CONFIGURATION_DRIFT         → Deny: runtime config differs from approved
CIRCUIT_BREAKER_OPEN        → Deny: service in fault state
```

---

## Trust Boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│                    TRUSTED ZONE                                   │
│                                                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐         │
│  │ Policy YAML │  │ Allowed     │  │ Approved model    │         │
│  │             │  │ signers     │  │ digests           │         │
│  └─────────────┘  └─────────────┘  └──────────────────┘         │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │              POLICY ENGINE (fail-closed)                  │     │
│  └──────────────────────────┬──────────────────────────────┘     │
└─────────────────────────────┼───────────────────────────────────┘
                              │ GATE DECISION
┌─────────────────────────────┼───────────────────────────────────┐
│                    UNTRUSTED ZONE                                 │
│                              ↓                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ Model    │  │ Tokenizer│  │ Container │  │ External       │  │
│  │ registry │  │ files    │  │ image     │  │ dependencies   │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────┘  │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│  │ VEX docs │  │ Scan     │  │ Runtime  │                      │
│  │          │  │ results  │  │ config   │                      │
│  └──────────┘  └──────────┘  └──────────┘                      │
└─────────────────────────────────────────────────────────────────┘
```

**Key principle**: Everything outside the policy engine and its trusted inputs is treated as potentially compromised. The gate never assumes integrity — it verifies.

---

## Residual Risks

| Risk | Description | Status |
|------|-------------|--------|
| Policy misconfiguration | Overly permissive policy (e.g., `require_signature: false`) weakens all signature-based mitigations | Mitigated by profile separation; industrial profile enforces strict policy |
| Key compromise | If a signing key in the allowed-signer list is compromised, an attacker can forge valid signatures | Partially mitigated by evidence freshness (24h) and key rotation guidance |
| Insider with policy access | An insider who can modify `policy.yaml` can weaken gates | Out of scope (requires organizational access controls) |
| Zero-day in verification code | Bug in signature/hash verification could accept invalid proofs | Mitigated by using well-tested libraries (cryptography, hashlib) |
| Model behavior attacks | Backdoors that don't change file hashes (e.g., training-time attacks) | Out of scope for BOM+provenance approach; requires ML-specific defenses |
| Time-of-check/time-of-use | Gap between gate evaluation and actual deployment | Mitigated by runtime configuration digest verification |
