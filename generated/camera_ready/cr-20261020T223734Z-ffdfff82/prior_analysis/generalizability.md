# Generalizability

**Audit status:** OBSERVED FROM RAW DATA + INFERRED FROM CODE  
**Sources:** `config/profiles/`, `src/traceai/campaigns/rq4.py`, `results/`, `README.md`

---

## 1. Models Tested

| Model | Parameters | Architecture | Tested? | Evidence |
|-------|-----------|-------------|---------|---------|
| sshleifer/tiny-gpt2 | ~2M | GPT-2 (decoder-only) | YES | `results/rq4/rq4-20260722-133959-e395d20d/` + stress campaigns (OBSERVED) |
| openai-community/gpt2 | 124M | GPT-2 (decoder-only) | NO — planned only | `rq4.py:FULL_MODEL` + `config/profiles/gpu.yaml` — GPU campaign not executed |
| GPT-2 variants (medium/large/xl) | 345M–1.5B | GPT-2 | NOT PRESENT | No configuration or code references |
| Llama (any version) | — | Llama (decoder-only) | NOT PRESENT | — |
| Mistral | — | Mistral | NOT PRESENT | — |
| Falcon | — | Falcon | NOT PRESENT | — |
| Other architectures | — | — | NOT PRESENT | — |

**Conclusion:** Only `sshleifer/tiny-gpt2` was actually tested in existing campaigns. `openai-community/gpt2` is configured but the GPU campaign was never executed.

---

## 2. Hardware Configurations Tested

| Hardware | GPU | CUDA | Tested? | Evidence |
|---------|-----|------|---------|---------|
| Windows workstation CPU | None | No | YES | All CPU campaigns (OBSERVED) |
| NVIDIA L4 GPU | L4 (24GB) | Yes | NO — planned | `config/profiles/gpu.yaml` (INFERRED FROM CODE) |
| Other NVIDIA GPUs | — | — | NOT PRESENT | — |
| AMD GPU | — | ROCm | NOT PRESENT | — |
| Apple Silicon (MPS) | — | Metal | NOT PRESENT | — |
| Multi-GPU | — | — | NOT PRESENT | — |

---

## 3. Operating Systems Tested

| OS | Tested? | Evidence |
|----|---------|---------|
| Windows 11 (local) | YES | All campaigns, `generated/doctor_report.json` (OBSERVED) |
| Linux | NOT OBSERVED | `scripts/run_gpu_campaign.sh` exists (shell script for Linux) but no campaign evidence |
| macOS | NOT PRESENT | — |

---

## 4. Python / PyTorch Versions

| Component | Value | Evidence |
|----------|-------|---------|
| Python | 3.11.6 | `generated/doctor_report.json` + `generated/article/section_5_1_final.tex` (OBSERVED) |
| PyTorch | 2.13.0+cpu | `results/rq1/rq1-20260722-140850-18433df2/ground_truth_graph.json` (OBSERVED) |
| Other Python versions | Not tested | — |
| Other PyTorch versions | Not tested | — |

---

## 5. Deployment Profiles Tested

| Profile | Tested? | Evidence |
|---------|---------|---------|
| `local` (CPU, Windows) | YES | All campaigns |
| `gpu` (NVIDIA L4) | NO — planned | GPU campaign failed; `config/profiles/gpu.yaml` |
| `container` (Docker) | NOT EXECUTED | `config/profiles/container.yaml` exists; no campaign |
| `industrial` (Harbor + K3s + Dependency-Track) | NOT EXECUTED | `config/profiles/industrial.yaml` exists; no campaign |

---

## 6. Limitations on Generalizability

The following generalizations CANNOT be made from existing evidence:

1. **Billion-parameter models:** Only tiny-gpt2 (2M) was tested in executed campaigns. Latency, GPU memory, and circuit breaker behavior at scale are unknown.

2. **Non-GPT-2 architectures:** The BOM generation code (`rq1_finalizer.py`) is generic, but performance claims on latency, memory, or throughput are only valid for GPT-2 family models.

3. **GPU inference:** No GPU campaign data exists. All latency numbers come from CPU-only inference.

4. **Container/Kubernetes deployment:** The container and industrial profiles were never executed. Container-level attestation via cosign (`results/cosign/`) was partially tested but not integrated into a full campaign.

5. **Other operating systems:** All experiments ran on Windows 11. Linux/macOS behavior may differ due to path handling, process management, and NVML availability.

6. **Multi-tenant or distributed serving:** The inference service (`src/traceai/service/app.py`) is a single-process FastAPI app. Multi-worker or distributed deployments are not tested.

---

## 7. README Acknowledgment

The project's own `README.md` documents these limitations:

> "GPT-2 as proxy for production LLMs. We use GPT-2 (124M parameters) as a representative open-weight model. Results on latency overhead and BOM structure may not generalize to billion-parameter models served on multi-GPU clusters."

> "Local profile limitations. The local execution profile simulates registry and vulnerability-tracking behavior without real Harbor, K3s, or Dependency-Track instances."

These are OBSERVED limitations, not extrapolations.
