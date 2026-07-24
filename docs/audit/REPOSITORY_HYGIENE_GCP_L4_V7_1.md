# Repository Hygiene Audit — traceai-gcp-l4-ready-v7.1

**Date:** 2026-07-24  
**Baseline commit:** 62a33987a772f3a6eeb23dd2fd925ca116644b25  
**Baseline tag:** traceai-gcp-l4-ready-v7  
**Branch:** repo-hygiene-gcp-l4-v7-1  

---

## Tracked File Inventory

| Category | Count | Examples |
|----------|-------|---------|
| TRACKED_SOURCE | ~50 | `src/traceai/**/*.py` |
| TRACKED_DOCUMENTATION | 9 | `README.md`, `docs/*.md` |
| TRACKED_TEST | 14 | `tests/unit/*.py`, `tests/integration/*.py` |
| TRACKED_CONFIG | 12 | `config/**/*.yaml`, `pyproject.toml`, `requirements*` |
| TRACKED_FIXTURE | 12 | `fixtures/**/*` |
| TRACKED_SCRIPT | 17 | `scripts/*.ps1`, `scripts/*.py`, `scripts/*.sh` |
| TRACKED_CI | 2 | `.github/workflows/tests.yml`, `ci/gitlab-ci.yml` |
| TRACKED_INFRA | 8 | `docker/*`, `manifests/**/*` |
| TRACKED_META | 8 | `.editorconfig`, `.gitattributes`, `CITATION.cff`, etc. |

## Ignored File Inventory

| Category | Path | Classification | Action |
|----------|------|----------------|--------|
| .venv/ | Virtual environment | IGNORED_CACHE | Preserve (not deleted) |
| .tools/ | Portable binaries | IGNORED_CACHE | Preserve |
| .pytest_cache/ | Test cache | IGNORED_CACHE | SAFE_TO_DELETE |
| `__pycache__/` (multiple) | Bytecode cache | IGNORED_CACHE | SAFE_TO_DELETE |
| src/traceai.egg-info/ | Package metadata | IGNORED_CACHE | SAFE_TO_DELETE |
| workspace/ | Runtime workspace (keys, logs) | IGNORED_EVIDENCE | Preserve |
| generated/ | All generated outputs | IGNORED_EVIDENCE | Preserve (science data) |
| generated/gpu_l4/ | L4 adaptation inventory | IGNORED_EVIDENCE | Distill into this doc |
| generated/rq1/ | RQ1 BOM evidence | IGNORED_EVIDENCE | Preserve |
| generated/rq3/ | RQ3 VEX/scanner evidence | IGNORED_EVIDENCE | Preserve |
| generated/rq4/ | RQ4 control activation evidence | IGNORED_EVIDENCE | Preserve |
| generated/article/ | Article fragments | IGNORED_EVIDENCE | Preserve |
| generated/audit/ | Audit data | IGNORED_EVIDENCE | Preserve |
| generated/reproducibility/ | Repro validation | IGNORED_EVIDENCE | Preserve |
| results/ | Campaign results (all) | IGNORED_EVIDENCE | Preserve |
| paper/fragments/environment_gpu.tex | GPU LaTeX fragment | IGNORED_EVIDENCE | Preserve (regenerable) |

## Superseded Files

| File | Classification | Action |
|------|----------------|--------|
| docs/GPU_CAMPAIGN_RTX_A5000.md | SUPERSEDED | Remove (git rm) |

## Branches

| Branch | Merged into main? | Action |
|--------|-------------------|--------|
| adapt-nvidia-l4 | Yes (same commit) | Delete local branch |

## Key Findings from Inventory Searches

### RTX A5000 references in tracked files:
- `docs/GPU_CAMPAIGN_RTX_A5000.md` — superseded historical redirect → **remove**
- `tests/unit/test_gpu_l4_adaptation.py` — asserts A5000 is NOT required → **keep** (negative assertions)

### Hard-coded CUDA wheels:
- No `cu121` references found
- No `download.pytorch.org/whl/cu[0-9]+` in active code

### Placeholders:
- No `<PENDING>` in tracked files (only in ignored `paper/fragments/environment_gpu.tex`)

### .gitignore policy issue:
- `results/` blanket ignore prevents tracking `results/public/` content
- Re-inclusion rules only cover `.gitkeep` files

---

## Distilled Information from Generated Reports

### NVIDIA L4 Adaptation (from generated/gpu_l4/l4_adaptation_inventory.md)

- `config/profiles/gpu.yaml`: Updated to NVIDIA L4 (regex: "NVIDIA L4", min VRAM: 22000 MB)
- `scripts/run_gpu_campaign.sh`: Updated to profile-driven, hardware-agnostic validation
- `docs/GPU_CAMPAIGN_NVIDIA_L4.md`: Complete L4 runbook
- All active code uses profile regex instead of hard-coded GPU names

### Python 3.12 Compatibility (from generated/gpu_l4/python_compatibility_report.md)

- GCP node runs Python 3.12.3
- `pyproject.toml` declares `requires-python = ">=3.10,<3.13"` — compatible
- All declared dependencies support Python 3.12
- `tool.ruff.target-version = "py311"` is cosmetic (lint only)

### Publication Readiness (from generated/publication_readiness.json)

| Claim | Status |
|-------|--------|
| RQ1: BOM coverage | SUPPORTED_QUICK_ONLY |
| RQ2: Cryptographic tamper detection | SUPPORTED_QUICK_ONLY |
| RQ3: Scanner agreement and VEX triage | SUPPORTED_QUICK_ONLY |
| RQ4: Runtime overhead and drift | UNSUPPORTED (requires GPU) |
| RQ4: GPU metrics | BLOCKED_GPU |
| Industrial claims | BLOCKED_EXTERNAL_INFRASTRUCTURE |

---

## Disposable Items Deleted

| Path | Reason |
|------|--------|
| .pytest_cache/ | Test runner cache, regenerable |
| scripts/__pycache__/ | Bytecode cache |
| src/traceai/__pycache__/ | Bytecode cache |
| src/traceai/analysis/__pycache__/ | Bytecode cache |
| src/traceai/bom/__pycache__/ | Bytecode cache |
| src/traceai/campaigns/__pycache__/ | Bytecode cache |
| src/traceai/faults/__pycache__/ | Bytecode cache |
| src/traceai/policy/__pycache__/ | Bytecode cache |
| src/traceai/provenance/__pycache__/ | Bytecode cache |
| src/traceai/service/__pycache__/ | Bytecode cache |
| src/traceai/vulnerability/__pycache__/ | Bytecode cache |
| tests/__pycache__/ | Bytecode cache |
| tests/integration/__pycache__/ | Bytecode cache |
| tests/unit/__pycache__/ | Bytecode cache |
| src/traceai.egg-info/ | Package build metadata, regenerable |

## Files Deliberately Retained

| File | Reason |
|------|--------|
| docs/GPU_CAMPAIGN_NVIDIA_L4.md | Active L4 runbook |
| config/profiles/gpu.yaml | Active GPU profile |
| scripts/run_gpu_campaign.sh | Active campaign executor |
| scripts/phase5_gpu_runbook.py | GPU preflight validator |
| tests/unit/test_gpu_l4_adaptation.py | Validates L4 adaptation |
| generated/ (all) | Scientific evidence, not tracked |
| results/ (all) | Campaign results, not tracked |
| workspace/ | Runtime data, not tracked |
| .venv/ | Development environment |
| .tools/ | Portable tool binaries |
