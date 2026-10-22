# TraceAI System Architecture

## Overview

TraceAI is the experimental artifact for the AI-SSS 2026 paper *"Operational Assurance for Secure Generative AI Supply Chains with CycloneDX"*. It implements a complete pipeline for generating, signing, verifying, and enforcing CycloneDX AI/ML Bills of Materials for LLM inference services, along with experiment campaigns to evaluate security and availability properties.

---

## Source Layout

```
src/traceai/
├── __init__.py            # Package version and exports
├── __main__.py            # python -m traceai entry point
├── cli.py                 # argparse-based CLI (doctor, serve, bom, campaign, analyze)
├── settings.py            # Pydantic-settings for env+.env loading
├── environment.py         # System detection, GPU probe, doctor report
├── hashing.py             # Deterministic SHA-256 for files, JSON, directories
├── logging_config.py      # Structured YAML-driven logging
├── models.py              # Shared data models (TrialResult, CampaignManifest, etc.)
│
├── service/               # FastAPI inference service with runtime controls
│   ├── app.py             # Lifespan, routes (/generate, /health, /ready, /metrics)
│   ├── inference.py       # Model loading, generation (torch + transformers)
│   ├── controls.py        # Rate limiter, circuit breaker, timeout, concurrency
│   ├── queueing.py        # Bounded request queue
│   └── telemetry.py       # In-memory metrics collector (latency, tokens, errors)
│
├── bom/                   # CycloneDX BOM generation and validation
│   ├── ground_truth.py    # Constructs ground-truth dependency graph
│   ├── cyclonedx_builder.py  # Produces CycloneDX JSON from ground truth
│   ├── normalization.py   # Normalizes BOM components for comparison
│   ├── validators.py      # Schema and structural validation
│   └── bom_link.py        # BOM-link resolution and cross-referencing
│
├── provenance/            # Cryptographic signing and attestation
│   ├── signer.py          # Key generation, signing (local-ephemeral or cosign)
│   ├── verifier.py        # Signature and attestation verification
│   └── attestations.py    # In-toto attestation creation and subject binding
│
├── policy/                # Deployment gate policy engine
│   ├── engine.py          # Rule evaluation engine (fail-closed by default)
│   └── decisions.py       # Gate decision types, factory, logging
│
├── vulnerability/         # Vulnerability scanning and VEX processing
│   ├── scanners.py        # Trivy/Grype/Syft orchestration
│   ├── vex.py             # CycloneDX VEX parsing, validation, filtering
│   └── normalize.py       # CVE normalization and deduplication
│
├── faults/                # Fault injection for experiment scenarios
│   ├── injector.py        # Fault injection functions (tamper model, swap tokenizer, etc.)
│   └── restore.py         # Workspace restoration after fault injection
│
├── campaigns/             # Experiment campaign orchestration
│   ├── security.py        # Security campaign (S0–S5, S8–S10)
│   ├── availability.py    # Availability campaign (S6–S7, S11)
│   └── overhead.py        # Overhead measurement campaign
│
└── analysis/              # Post-experiment analysis and artifact generation
    ├── statistics.py      # Wilson CI, bootstrap CI, Wilcoxon, percentiles
    ├── tables.py          # LaTeX/Markdown table generation
    ├── figures.py         # Matplotlib figure generation
    ├── narrative.py       # Automated narrative fragment generation
    └── sanitization.py    # Result sanitization for publication
```

---

## Module Responsibilities

### `service` — LLM Inference Service

The service module exposes a FastAPI HTTP service that wraps GPT-2 (or any HuggingFace model) for text generation. It enforces runtime controls that are verifiable via configuration digests:

- **app.py**: Application lifecycle, route definitions, configuration digest endpoint
- **inference.py**: Model loading with device auto-detection, async generation
- **controls.py**: Manages `max_new_tokens`, `timeout_seconds`, `max_concurrency`, `queue_depth`, `rate_limit_rpm`, and a circuit breaker (threshold + cooldown)
- **queueing.py**: Bounded FIFO queue with backpressure (HTTP 503 when full)
- **telemetry.py**: Tracks latency distributions, token counts, error rates in memory

### `bom` — Bill of Materials Generation

Generates CycloneDX AI/ML BOMs capturing the complete dependency graph of the inference pipeline:

- **ground_truth.py**: Enumerates Python packages, model files, tokenizer, datasets, and system dependencies into a ground-truth graph
- **cyclonedx_builder.py**: Serializes the graph into CycloneDX 1.6 JSON with AI/ML extensions
- **normalization.py**: Canonicalizes component names, versions, and PURLs for comparison
- **validators.py**: Validates BOMs against CycloneDX JSON Schema
- **bom_link.py**: Resolves bomLink references across nested BOMs

### `provenance` — Signing and Attestation

Manages cryptographic evidence binding artifacts to their approved state:

- **signer.py**: Creates signing keys (local-ephemeral for dev, cosign-keyless for production)
- **verifier.py**: Verifies signatures against allowed fingerprints, checks freshness
- **attestations.py**: Creates in-toto style attestations with subjects (model digest, BOM digest, config digest)

### `policy` — Deployment Gate Engine

Evaluates whether a deployment should proceed based on provenance, vulnerability, and runtime evidence:

- **engine.py**: Rule-based engine with fail-closed semantics, evaluates all policy sections and returns aggregate decision
- **decisions.py**: Typed gate decisions (APPROVED, DIGEST_MISMATCH, INVALID_SIGNATURE, etc.) with structured logging

### `vulnerability` — Scanning and VEX

Orchestrates vulnerability scanners and processes VEX documents for alert triage:

- **scanners.py**: Invokes Syft (SBOM generation), Grype, and Trivy (vulnerability scanning), normalizes output
- **vex.py**: Parses CycloneDX VEX documents, validates schema/signature/expiry/component-linking
- **normalize.py**: Deduplicates CVEs across scanners, normalizes severity ratings

### `faults` — Fault Injection

Provides controlled mutations for experiment scenarios:

- **injector.py**: Functions for each fault type: model weight tampering, tokenizer substitution, dataset manifest alteration, invalid/unauthorized signatures, missing attestation fields, substituted external models
- **restore.py**: Restores workspace to pre-fault state using FaultContext snapshots

### `campaigns` — Experiment Orchestration

Runs structured experiment campaigns with controlled trials:

- **security.py**: Iterates security scenarios (S0–S5, S8–S10) over N trials, records gate decisions
- **availability.py**: Runs availability scenarios (S6–S7, S11) against a live service, measures latency/throughput
- **overhead.py**: Measures BOM generation time, signing overhead, and policy evaluation cost

### `analysis` — Statistical Analysis and Artifacts

Processes raw results into publication-ready artifacts:

- **statistics.py**: Wilson confidence intervals, block bootstrap, Wilcoxon signed-rank test, percentile computation
- **tables.py**: Generates LaTeX and Markdown tables for paper inclusion
- **figures.py**: Produces matplotlib charts (latency distributions, detection rates, overhead comparisons)
- **narrative.py**: Auto-generates text fragments summarizing results for paper sections
- **sanitization.py**: Redacts hostnames, paths, and sensitive data from public results

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        PREPARATION PHASE                                 │
│                                                                         │
│  [Model Download] → [BOM Generation] → [Signing] → [Attestation]       │
│       ↓                    ↓                ↓             ↓              │
│  workspace/models    generated/*.cdx.json  *.sig     attestation.json   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                        GATE EVALUATION                                   │
│                                                                         │
│  [Artifacts] + [Policy Config] → [Policy Engine] → Gate Decision        │
│       ↓                                                                  │
│  APPROVED / DENIED (with reason code)                                    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                        RUNTIME PHASE                                     │
│                                                                         │
│  [Service Start] → [Config Digest Lock] → [Request Handling]            │
│       ↓                    ↓                      ↓                      │
│  Model loaded      config.sha256          Controls enforce limits        │
│                                           Telemetry records metrics      │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                        EXPERIMENT PHASE                                   │
│                                                                         │
│  [Fault Injection] → [Gate Re-evaluation / Load Test] → [Restore]       │
│       ↓                         ↓                           ↓            │
│  Mutated workspace      TrialResult (pass/fail/metrics)   Clean state    │
│                                 ↓                                        │
│  results/raw/{campaign_id}/trial-{N}.json                               │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                        ANALYSIS PHASE                                    │
│                                                                         │
│  [Raw Results] → [Statistics] → [Tables + Figures + Narratives]          │
│       ↓                ↓                    ↓                            │
│  results/raw/   results/normalized/   generated/ + paper/fragments/      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Profile System

TraceAI supports three execution profiles, selected via `TRACEAI_PROFILE` environment variable or `--profile` CLI flag:

| Profile      | Purpose                          | External Dependencies         |
|-------------|----------------------------------|-------------------------------|
| `local`     | Native Windows dev/research      | None (all optional)           |
| `container` | Docker-based isolated execution  | Docker runtime                |
| `industrial`| Full CI/CD pipeline validation   | Harbor, GitLab, K3s, Cosign, Dependency-Track |

Profile configuration files are at `config/profiles/{profile}.yaml` and define:

- **runtime**: Device selection, model ID, resource safety limits
- **service**: Host, port, workers, container image, registry
- **inference**: Control parameters (tokens, timeout, concurrency, circuit breaker)
- **signing**: Method (local-ephemeral vs cosign-keyless), key location, validity
- **scanning**: Which tools are required vs optional
- **external**: Which external services are enabled and their URLs
- **campaigns**: Trial counts, request counts, warmup parameters

The profile cascades with environment variables: `.env` → profile YAML → `TRACEAI_*` env vars (highest precedence).

---

## Configuration Loading

Configuration loading follows a layered architecture managed by `settings.py`:

1. **`TraceAISettings` (Pydantic BaseSettings)**: Loads from environment variables prefixed `TRACEAI_` and `.env` file. Provides typed, validated access to core settings.

2. **`load_profile_config(profile)`**: Reads `config/profiles/{profile}.yaml` for profile-specific parameters not in environment.

3. **`load_experiment_config()`**: Reads `config/experiment.yaml` defining scenarios, configurations, research questions, and safety limits.

4. **`load_policy_config()`**: Reads `config/policy.yaml` defining gate rules, provenance requirements, vulnerability thresholds, and decision actions.

5. **`config/logging.yaml`**: Structured logging configuration loaded by `logging_config.py`.

### Lock Files

- **`model.lock.json`**: Pins model repository, revision, and file hashes
- **`tools.lock.json`**: Pins external CLI tool versions and SHA-256 checksums
- **`requirements.lock`**: Pins all Python dependencies with exact versions

### Configuration Digest

At runtime, the service computes a SHA-256 digest over its active configuration. This digest is:
- Included in every inference response
- Compared against the approved digest during gate evaluation
- Used to detect configuration drift (scenario S6a–S6c)
