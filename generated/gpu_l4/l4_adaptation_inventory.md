# NVIDIA L4 Adaptation Inventory

**Generated:** 2026-07-23T15:04:11-03:00
**Baseline:** commit 66284be51872445ce66544b3eb0a893cb4aca227 (traceai-gpu-ready-v6)
**Target:** NVIDIA L4 on GCP node gcp-m4-insp-2

## Summary

All references to "RTX A5000" in the repository have been classified below.
Active configuration and validation code must be updated. Documentation
and historical references are handled according to their category.

## Matches by File

### config/profiles/gpu.yaml

| Line | Content | Classification | Action |
|------|---------|----------------|--------|
| 2 | `description: "RTX A5000 GPU execution..."` | Active configuration | Update to NVIDIA L4 |

### docs/GPU_CAMPAIGN_RTX_A5000.md

| Line | Content | Classification | Action |
|------|---------|----------------|--------|
| 1 | `# GPU Campaign Runbook — NVIDIA RTX A5000` | Documentation | Rename file, update content |
| 5 | `**GPU:** NVIDIA RTX A5000 (24 GB VRAM)` | Documentation | Update to NVIDIA L4 |
| 75 | `GPU: RTX A5000` | Documentation | Update to NVIDIA L4 |
| 173 | `Results from this node will be labeled: "NVIDIA RTX A5000..."` | Documentation | Update to NVIDIA L4 |

### scripts/run_gpu_campaign.sh

| Line | Content | Classification | Action |
|------|---------|----------------|--------|
| 3 | `# TraceAI RTX A5000 GPU Campaign Execution` | Active validation | Update header |
| 21 | `echo "  TraceAI RTX A5000 GPU Campaign"` | Active validation | Update banner |
| 203 | `# Gate 2: Device name contains RTX A5000` | Active validation | Use profile regex |
| 207 | `if "RTX A5000" not in device_name:` | Active validation | Use profile regex |
| 208 | `errors.append(f"...does not contain 'RTX A5000'")` | Active validation | Use profile regex |
| 278 | `print("  ✓ Device name contains 'RTX A5000'")` | Active validation | Use profile regex |

### scripts/run_gpu_campaign.sh (TORCH_INDEX_URL)

| Line | Content | Classification | Action |
|------|---------|----------------|--------|
| 158 | `if [ -z "${TORCH_INDEX_URL:-}" ]; then` | Active validation | Keep (correct behavior) |
| 174 | `echo "    TORCH_INDEX_URL=...cu124..."` | Active validation | Remove hard-coded example or make generic |

### docs/GPU_CAMPAIGN_RTX_A5000.md (TORCH_INDEX_URL)

| Line | Content | Classification | Action |
|------|---------|----------------|--------|
| 54 | `export TORCH_INDEX_URL=.../<cuXXX>` | Documentation | Keep (already generic) |

### docs/WINDOWS_SETUP.md (TORCH_INDEX_URL)

| Line | Content | Classification | Action |
|------|---------|----------------|--------|
| 184 | `pip install torch --index-url $env:TORCH_INDEX_URL` | Documentation | Keep (already generic) |
| 295 | `pip install torch --index-url $env:TORCH_INDEX_URL` | Documentation | Keep (already generic) |

## Additional Patterns Searched (No Matches)

| Pattern | Matches |
|---------|---------|
| `expected_gpu` | 0 |
| `minimum_vram` | 0 |
| `cu121` | 0 |
| `download.pytorch.org/whl/cu[0-9]+` (active code) | 1 (cu124 example in help text) |

## Classification Legend

| Category | Meaning | Policy |
|----------|---------|--------|
| Active configuration | Loaded at runtime by the application | Must update |
| Active validation | Checked during preflight/campaign | Must generalize |
| Documentation | Human-readable guides | Update to reflect NVIDIA L4 |
| Manuscript text | Paper fragments | Update future claims, preserve historical |
| Historical reference | Past experiment descriptions | Mark as historical, do not delete |
| Generated artifact | Output of previous runs | Will be regenerated |
| Test fixture | Test data | Update if asserting GPU name |
