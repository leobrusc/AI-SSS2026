# Evidence Graph Schema

**Audit status:** OBSERVED IMPLEMENTATION + PROPOSED FORMALIZATION  
**Sources:**  
- `results/rq1/rq1-20260722-140850-18433df2/ground_truth_graph.json` (31 nodes, 28 edges)  
- `results/rq1/rq1-20260722-140850-18433df2/linked_graph.json` (2 BOM-Link connections)  
- `generated/rq1/final_ml_bom.cdx.json` (6 ML-BOM components)  
- `generated/rq1/final_obom.cdx.json` (7 OBOM components)  
- `src/traceai/bom/bom_link.py` (BomLinkBuilder)  
- `src/traceai/bom/ground_truth.py`

---

## OBSERVED IMPLEMENTATION

### Node Inventory (ground_truth_graph.json)

Total nodes: 31. Applicable nodes (not NOT_APPLICABLE): 29.

#### ML-BOM Nodes (6 applicable)

| id | type | name | domain | applicability |
|----|------|------|--------|--------------|
| model-gpt2 | model | openai-community/gpt2 | mlbom | REQUIRED |
| model-weights | weight | model.safetensors | mlbom | REQUIRED |
| tokenizer | tokenizer | tokenizer.json | mlbom | REQUIRED |
| model-config | dataset | config.json | mlbom | REQUIRED |
| generation-config | dataset | generation_config.json | mlbom | REQUIRED |
| dataset-manifest | dataset | fixtures/datasets/manifest.json | mlbom | REQUIRED |

#### SBOM Nodes (16 applicable — from finalizer; 17 in raw ground-truth)

| id | type | name | domain |
|----|------|------|--------|
| pytorch | package | torch==2.13.0+cpu | sbom |
| transformers-pkg | package | transformers==5.14.1 | sbom |
| pkg-tokenizers | package | tokenizers==0.22.2 | sbom |
| pkg-fastapi | package | fastapi==0.139.2 | sbom |
| pkg-uvicorn | package | uvicorn==0.51.0 | sbom |
| pkg-pydantic | package | pydantic==2.13.4 | sbom |
| pkg-pydantic-settings | package | pydantic-settings==2.14.2 | sbom |
| pkg-httpx | package | httpx==0.28.1 | sbom |
| pkg-pyyaml | package | pyyaml==6.0.3 | sbom |
| pkg-pandas | package | pandas==3.0.3 | sbom |
| pkg-numpy | package | numpy==2.4.4 | sbom |
| pkg-scipy | package | scipy==1.17.1 | sbom |
| pkg-matplotlib | package | matplotlib==3.11.1 | sbom |
| pkg-psutil | package | psutil==7.2.2 | sbom |
| pkg-jsonschema | package | jsonschema==4.26.0 | sbom |
| pkg-cryptography | package | cryptography==49.0.0 | sbom |

#### HBOM Nodes (4 defined; 2 NOT_APPLICABLE)

| id | type | name | domain | applicability |
|----|------|------|--------|--------------|
| python-runtime | runtime | python 3.11.6 | hbom | REQUIRED |
| os-platform | runtime | Windows 10 | hbom | REQUIRED |
| host-cpu | hardware | CPU | hbom | REQUIRED |
| host-ram | hardware | RAM 31.5GB | hbom | REQUIRED |
| host-gpu | hardware | GPU | hbom | NOT_APPLICABLE |
| cuda-runtime | runtime | CUDA | hbom | NOT_APPLICABLE |

#### OBOM Nodes (3 in raw ground-truth; finalizer extends to 5+)

| id | type | name | domain |
|----|------|------|--------|
| inference-service | service | traceai-inference 0.1.0 | obom |
| runtime-policy | policy | config/policy.yaml | obom |
| traceai-app | service | traceai 0.1.0 | obom + sbom |

**Note:** The finalizer (`rq1_finalizer.py`) generates an extended OBOM (`final_obom.cdx.json`) with 7 components (obom-service, obom-policy, obom-snapshot, obom-os, obom-python, obom-cpu, obom-ram). This is richer than the raw ground-truth OBOM.

---

### Edge Inventory (ground_truth_graph.json — 28 edges)

| source | target | relationship | domain |
|--------|--------|-------------|--------|
| inference-service | traceai-app | dependsOn | obom |
| traceai-app | model-gpt2 | dependsOn | mlbom |
| model-gpt2 | tokenizer | uses | mlbom |
| model-gpt2 | model-weights | contains | mlbom |
| model-gpt2 | model-config | describedBy | mlbom |
| model-gpt2 | generation-config | describedBy | mlbom |
| model-gpt2 | dataset-manifest | evaluatedWith | mlbom |
| traceai-app | pytorch | dependsOn | sbom |
| traceai-app | transformers-pkg | dependsOn | sbom |
| traceai-app | pkg-tokenizers | dependsOn | sbom |
| traceai-app | pkg-fastapi | dependsOn | sbom |
| traceai-app | pkg-uvicorn | dependsOn | sbom |
| traceai-app | pkg-pydantic | dependsOn | sbom |
| traceai-app | pkg-pydantic-settings | dependsOn | sbom |
| traceai-app | pkg-httpx | dependsOn | sbom |
| traceai-app | pkg-pyyaml | dependsOn | sbom |
| traceai-app | pkg-pandas | dependsOn | sbom |
| traceai-app | pkg-numpy | dependsOn | sbom |
| traceai-app | pkg-scipy | dependsOn | sbom |
| traceai-app | pkg-matplotlib | dependsOn | sbom |
| traceai-app | pkg-psutil | dependsOn | sbom |
| traceai-app | pkg-jsonschema | dependsOn | sbom |
| traceai-app | pkg-cryptography | dependsOn | sbom |
| pytorch | python-runtime | dependsOn | hbom |
| python-runtime | os-platform | runsOn | hbom |
| inference-service | runtime-policy | governedBy | obom |
| inference-service | host-cpu | deployedOn | hbom |
| inference-service | host-ram | uses | hbom |

**Relationship types observed:**
- `dependsOn` (SBOM + OBOM)
- `uses` (MLBOM)
- `contains` (MLBOM)
- `describedBy` (MLBOM)
- `evaluatedWith` (MLBOM)
- `runsOn` (HBOM)
- `governedBy` (OBOM)
- `deployedOn` (HBOM)

---

### BOM-Link Cross-Document Connections (linked_graph.json)

Only 2 inter-BOM links are recorded in the campaign output:

| source BOM serial | target BOM serial | link type | relationship |
|------------------|------------------|-----------|-------------|
| urn:uuid:8cf19153... (ML-BOM) | urn:uuid:2559bc2a... (SBOM-Trivy) | sbom-trivy | dependsOn |
| urn:uuid:8cf19153... (ML-BOM) | urn:uuid:e9e82e27... (OBOM) | obom | describedBy |

The `BomLinkBuilder` class supports `link_sbom_to_ml_bom`, `link_hbom_to_ml_bom`, and `link_obom_snapshot`. Only the SBOM-Trivy and OBOM links are materialized in the campaign output.

---

### Identity Resolution Rules (OBSERVED)

From `src/traceai/bom/ground_truth.py` and `generated/rq1/identity_mapping.csv`:

| Identity type | When used | Example |
|--------------|-----------|---------|
| PURL (`pkg:pypi/...`) | Python packages | `pkg:pypi/torch@2.13.0+cpu` |
| PURL (`pkg:huggingface/...`) | ML models | `pkg:huggingface/openai-community/gpt2` |
| PURL (`pkg:generic/...`) | Python runtime | `pkg:generic/cpython@3.11.6` |
| name + version | Hardware nodes | CPU (no PURL standard) |
| SHA-256 digest | Artifact integrity | Used in attestations, not as primary node ID |
| `bom-ref` string | Cross-component references | `comp-model`, `comp-weights` |

No composite ID is enforced — each node uses the most specific available identifier. Hardware nodes use name/version only.

---

### Cross-Document Consistency Validation

**Status: PARTIALLY_IMPLEMENTED**

- `src/traceai/bom/validators.py` performs schema validation (CycloneDX schema conformance)
- No function verifies that a component appearing in the SBOM has a corresponding `bom-ref` in the ML-BOM or that the digest in the OBOM matches the attested digest in the attestation document
- The finalizer (`rq1_finalizer.py`) computes coverage by matching component names, not by verifying cross-document digest consistency
- `linked_graph.json` records BOM-to-BOM relationships but does not verify semantic consistency between the linked documents

---

## PROPOSED FORMALIZATION FOR PAPER

This section describes a formal graph model derived from the observed implementation. It is a **proposed formalization**, not a verbatim description of an existing formal specification in the codebase.

### Formal Graph Definition

Let `G = (V, E)` where:

**V** = set of typed nodes, partitioned into:
- `V_A` — Artifact nodes: model, weight, tokenizer, dataset, package
- `V_E` — Evidence nodes: attestation, signature envelope, VEX document
- `V_D` — Decision nodes: policy evaluation outcomes (GateDecision enum values)
- `V_R` — Runtime-observation nodes: process snapshot, configuration state, OBOM snapshot

**E** ⊆ V × V × L where L is a set of typed relation labels:

| Relation | Connects | Observed? |
|---------|---------|-----------|
| `DEPENDS_ON` | service → package, model → weight | YES (ground_truth_graph.json) |
| `USES` | model → tokenizer | YES |
| `CONTAINS` | model → weights | YES |
| `DESCRIBED_BY` | model → config, ML-BOM → OBOM | YES |
| `EVALUATED_WITH` | model → dataset | YES |
| `RUNS_ON` | python → os | YES |
| `DEPLOYED_ON` | service → CPU | YES |
| `GOVERNED_BY` | service → policy | YES |
| `SIGNED_BY` | artifact → attestation envelope | INFERRED (not stored as graph edge) |
| `ATTESTED_BY` | artifact → attestation predicate | INFERRED (not stored as graph edge) |
| `AFFECTED_BY` | component → CVE finding | NOT_STORED_AS_EDGE (in scanner output, not graph) |
| `DECIDED_BY` | attestation → gate decision | INFERRED (gate produces decision, not stored) |

**Identity function** `id: V_A → I` where `I = PURL | SHA256 | name@version`:
- Packages: PURL preferred (`pkg:pypi/...`, `pkg:huggingface/...`)
- Hardware: `name@version`
- Artifacts: SHA-256 digest (in attestation, not as primary ID)

**Note:** In the current implementation, `V_E`, `V_D`, and the `SIGNED_BY`, `ATTESTED_BY`, `DECIDED_BY` edges are not materialized as explicit graph nodes/edges. They are represented as data structures within attestation JSON files and campaign result records, but not as formal graph connections.
