# Mutable AI Artifacts

**Audit status:** INFERRED FROM CODE + OBSERVED FROM RAW DATA  
**Sources:** `fixtures/`, `src/traceai/`, `config/`, `results/`

---

## Classification Legend

| Status | Meaning |
|--------|---------|
| FULLY_TRACKED | Artifact has SHA-256 digest in attestation; change invalidates gate |
| PARTIALLY_TRACKED | Artifact present in BOM but not attested or digest not enforced |
| NOT_TRACKED | Artifact used at runtime with no BOM entry, digest, or gate check |

---

## 1. Prompt Variants and Templates

| Artifact | Files | Status | Notes |
|----------|-------|--------|-------|
| Smoke prompts | `fixtures/prompts/smoke.jsonl` | PARTIALLY_TRACKED | Listed in dataset manifest (`fixtures/datasets/manifest.json`); SHA-256 in manifest is a placeholder (static value, not computed from file content). Changes do not regenerate evidence or invalidate gate. |
| Long generation prompts | `fixtures/prompts/long_generation.jsonl` | PARTIALLY_TRACKED | Same as above. |
| Burst prompts | `fixtures/prompts/burst.jsonl` | NOT_TRACKED | Not in dataset manifest. |
| Sustained prompts | `fixtures/prompts/sustained.jsonl` | NOT_TRACKED | Not in dataset manifest. |
| RQ4 prompt corpus | `PROMPTS` list in `src/traceai/campaigns/rq4.py` (5 hardcoded strings) | PARTIALLY_TRACKED | Hash stored in `prompt_corpus_hash.json` per campaign run. Not attested in BOM. Change triggers new corpus hash but does not regenerate attestation or invalidate security gate. |

**Digest/gate behavior:** Prompt content changes do NOT invalidate the deployment gate. The gate checks model artifact digest, attestation completeness, and signer authorization — not prompt content.

---

## 2. System Prompts

| Artifact | Status | Notes |
|----------|--------|-------|
| System prompts | NOT_TRACKED | No system prompt mechanism exists in `InferenceEngine` or `FastAPI` app. GPT-2 is a causal LM without instruction-following infrastructure. No system prompt field in request schema. |

---

## 3. LoRA / PEFT Adapters

| Artifact | Status | Notes |
|----------|--------|-------|
| LoRA adapters | NOT_TRACKED | No LoRA or PEFT loading code in `src/traceai/service/inference.py` or anywhere in the codebase. `AutoModelForCausalLM.from_pretrained()` loads base weights only. |
| PEFT config | NOT_TRACKED | `peft` not in `requirements.txt`, `requirements.lock`, or `pyproject.toml`. |

---

## 4. Retrieval Indexes / Vector Databases / RAG

| Artifact | Status | Notes |
|----------|--------|-------|
| Vector store | NOT_TRACKED | No RAG infrastructure. No `faiss`, `chromadb`, `pinecone`, `weaviate`, or similar dependency. |
| Retrieval corpus | NOT_TRACKED | — |
| RAG pipeline | NOT_TRACKED | — |

---

## 5. Guardrails and Plugins

| Artifact | Status | Notes |
|----------|--------|-------|
| Input guardrails | NOT_TRACKED | No input validation beyond FastAPI request schema. No content filter, no toxicity classifier. |
| Output guardrails | NOT_TRACKED | No output filtering layer. |
| Plugins/tools | NOT_TRACKED | No plugin system. GPT-2 is a pure text generation model. |

---

## 6. Generation Settings

| Setting | Configured in | Status | Change detection |
|---------|--------------|--------|-----------------|
| `max_new_tokens` | `ControlsManager.max_new_tokens` (default 100) | FULLY_TRACKED (via config drift) | INV-5: `check_configuration_drift()` compares approved vs current config digest. Change triggers `CONFIGURATION_DRIFT`. |
| `timeout_seconds` | `ControlsManager.timeout_seconds` | FULLY_TRACKED (via config drift) | Same as above. |
| `max_concurrency` | `ControlsManager.max_concurrency` | FULLY_TRACKED (via config drift) | Same. |
| `rate_limit_rpm` | `ControlsManager.rate_limit_rpm` | FULLY_TRACKED (via config drift) | Same. |
| `circuit_breaker_threshold` | `ControlsManager.circuit_breaker_threshold` | FULLY_TRACKED (via config drift) | Same. |
| `temperature` | `InferenceEngine.generate()` parameter | NOT_TRACKED | Not in approved configuration. Not checked by gate. |
| `do_sample` | Derived from temperature | NOT_TRACKED | — |

---

## 7. Model Weights

| Artifact | Status | Evidence |
|----------|--------|---------|
| Model weights file | PARTIALLY_TRACKED | Digest attested in signed envelope (`create_attestation(model_digest=...)`). Gate checks digest match. However: in CPU campaigns, the model loaded is `sshleifer/tiny-gpt2` which is downloaded from HuggingFace Hub; actual on-disk file digest is not verified at inference time (attestation gate runs only at deployment initialization). |

---

## 8. Tokenizer Artifacts

| Artifact | Status | Evidence |
|----------|--------|---------|
| tokenizer.json | PARTIALLY_TRACKED | S2 scenario injects tokenizer substitution and detects via digest mismatch. However, the tracked artifact is a synthetic fixture file (`fixtures/approved/`), not the real tokenizer files from HuggingFace. |

---

## 9. Dataset Manifest

| Artifact | Status | Evidence |
|----------|--------|---------|
| `fixtures/datasets/manifest.json` | PARTIALLY_TRACKED | S3 scenario injects manifest alteration and detects via digest mismatch. SHA-256 values inside the manifest are static placeholders, not real hashes of actual files. |

---

## 10. Summary

| Artifact Class | Count | FULLY_TRACKED | PARTIALLY_TRACKED | NOT_TRACKED |
|---------------|-------|--------------|-------------------|------------|
| Prompt variants | 4 | 0 | 2 | 2 |
| System prompts | 0 | — | — | — |
| LoRA/PEFT | 0 | — | — | — |
| Retrieval/RAG | 0 | — | — | — |
| Guardrails/plugins | 0 | — | — | — |
| Generation settings | 6 | 5 (via config drift) | 0 | 1 (temperature) |
| Model weights | 1 | 0 | 1 | 0 |
| Tokenizer | 1 | 0 | 1 | 0 |
| Dataset manifest | 1 | 0 | 1 | 0 |

**Key finding:** The most mutable artifacts in a production LLM pipeline (prompts, RAG corpora, LoRA adapters, generation settings) are either absent (LoRA, RAG) or only partially tracked. Temperature, sampling strategy, and prompt templates are not tracked at all. The framework's tracking is strongest for runtime configuration parameters (C0–C3 via config drift) and weakest for soft artifacts (prompts, generation hyperparameters not in ControlsManager).
