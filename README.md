# TraceAI — Runtime-Aware Assurance for Dependable LLM Pipelines

**From Static AI/ML-BOMs to Runtime-Aware Assurance: An Industrial Experience with CycloneDX for Dependable LLM Pipelines**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![LADC 2026](https://img.shields.io/badge/Conference-LADC%202026-blue.svg)](#citation)

## Research Objective

This repository contains the replication package for the paper submitted to **LADC 2026** (Latin-American Dependable Computing Conference). The research investigates whether the CycloneDX AI/ML BOM specification—augmented with cryptographic attestations, VEX advisories, and runtime configuration controls—can provide end-to-end assurance for dependable LLM inference pipelines.

We propose **TraceAI**, a framework that extends static bill-of-materials (BOM) generation with runtime-aware integrity verification, vulnerability triage, and fault-injection campaigns to evaluate dependability properties of ML supply chains.

---

## Research Questions

| ID | Research Question | Focus |
|----|-------------------|-------|
| **RQ1** | To what extent does a CycloneDX AI/ML-BOM cover the ground-truth dependency graph of an LLM inference pipeline? | BOM completeness — component coverage, dependency-edge recall, and metadata fidelity against a manually curated ground-truth graph. |
| **RQ2** | Can cryptographic provenance and attestation gates ensure artifact integrity across the ML supply chain? | Integrity assurance — digital signatures, hash verification, and attestation gate pass/fail rates for model weights, datasets, and container images. |
| **RQ3** | How effective is VEX (Vulnerability Exploitability eXchange) at reducing actionable vulnerability alerts without masking true positives? | Alert reduction — precision, recall, and F1 of VEX-annotated triage versus raw CVE scanner output from Dependency-Track. |
| **RQ4** | What is the runtime overhead and fault-detection capability of configuration controls enforced at inference time? | Availability & overhead — latency/throughput impact of runtime guards and their ability to detect injected configuration faults. |

---

## Safety Statement

> **All experiments in this repository run on isolated, synthetic fixtures.**

- **No production systems** are targeted or accessed at any point.
- **No administrative privileges** are required to execute any experiment.
- All model downloads use publicly available checkpoints from Hugging Face Hub.
- Fault-injection campaigns operate exclusively on local inference processes with no network-facing exposure.
- Cryptographic operations use ephemeral keys generated per session; no real signing identities are involved.
- The `industrial` profile references external tools (Harbor, K3s, Dependency-Track) but **does not provision or modify** them—it only reads their APIs if pre-configured by the operator.

---

## Scientific Limitations

Readers and reviewers should consider the following scope constraints:

1. **GPT-2 as proxy for production LLMs.** We use GPT-2 (124M parameters) as a representative open-weight model. Results on latency overhead and BOM structure may not generalize to billion-parameter models served on multi-GPU clusters.

2. **Local profile limitations.** The `local` execution profile simulates registry and vulnerability-tracking behavior without real Harbor, K3s, or Dependency-Track instances. Claims about container-level attestation require validation under the `industrial` profile.

3. **No semantic-backdoor detection from BOM metadata alone.** CycloneDX metadata captures provenance and integrity signals but cannot detect adversarial weight manipulation (e.g., backdoor triggers embedded in model parameters). BOM-based assurance is necessary but not sufficient for model-level security.

4. **No industrial claim without industrial-profile evidence.** Findings from the `local` and `container` profiles inform feasibility but do not constitute industrial validation. Industrial claims require execution under the `industrial` profile with real infrastructure components.

---

## Prerequisites

### Windows Environment

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Python** | 3.11+ | CPython from [python.org](https://www.python.org/downloads/) or Microsoft Store |
| **Git** | 2.40+ | [git-scm.com](https://git-scm.com/download/win) |
| **PowerShell** | 5.1+ | Ships with Windows 10/11; PowerShell 7+ also supported |
| **NVIDIA GPU + CUDA** *(optional)* | CUDA 12.x+ | Required only for GPU-accelerated inference experiments |

### Optional Tools (for container/industrial profiles)

| Tool | Purpose |
|------|---------|
| Docker Desktop | Container profile execution |
| cosign | Container image signing and verification |
| syft / grype | SBOM generation and vulnerability scanning |
| Dependency-Track | Vulnerability management dashboard |

---

## Quick Start

From an empty `Documents` directory, clone the repository and bootstrap the environment:

```powershell
# Navigate to the project directory
Set-Location C:\Users\leolima\Documents\traceai-ladc2026

# Allow script execution for this session
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Bootstrap: creates .venv, installs dependencies, downloads GPT-2 fixtures
.\tasks.ps1 bootstrap -Profile local

# Verify environment: checks Python, GPU, dependencies, disk space
.\tasks.ps1 doctor -Profile local

# Run smoke tests: quick validation that all components work
.\tasks.ps1 smoke -Profile local
```

If all three commands succeed with green output, the environment is ready for experimentation.

---

## Virtual Environment

### Activation

```powershell
Set-Location C:\Users\leolima\Documents\traceai-ladc2026
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

You will see `(.venv)` prepended to your prompt, indicating the virtual environment is active.

### Deactivation

```powershell
deactivate
```

> **Note:** The `tasks.ps1` script automatically activates the virtual environment for each command. Manual activation is only needed for interactive exploration or debugging.

---

## Current Evidence Status

| Area | Status |
|------|--------|
| **RQ1–RQ3** | Real local-tool evidence completed; current public status is quick/local evidence. |
| **RQ4** | CPU diagnostic completed; NVIDIA L4 GPU campaign pending. |
| **Industrial profile** | Not executed — Harbor, K3s/Kubernetes, and Dependency-Track are not provisioned. |

---

## Execution Profiles

TraceAI supports four execution profiles that control infrastructure dependencies and experiment fidelity:

| Profile | Description | Infrastructure | Use Case |
|---------|-------------|---------------|----------|
| **`local`** | Fully self-contained on the developer machine. Uses file-system stubs for registry and vulnerability-tracker interactions. | None (Python + filesystem only) | Development, CI, replication review |
| **`gpu`** | Real CUDA inference and NVML telemetry on a dedicated GPU node. | NVIDIA GPU configured in `config/profiles/gpu.yaml` | RQ4 GPU publication evidence |
| **`container`** | Runs inference inside OCI containers with signed images. Requires Docker but no external services. | Docker Desktop | Container attestation experiments (RQ2) |
| **`industrial`** | Connects to real Harbor registry, K3s cluster, and Dependency-Track instance. Requires pre-provisioned infrastructure. | Harbor, K3s, Dependency-Track, cosign | Full industrial validation (all RQs) |

> **CPU fallback policy:** CPU fallback is permitted for local diagnostics and development.
> CPU fallback is **forbidden** when collecting GPU publication evidence (`gpu` profile).

Select a profile with the `-Profile` parameter:

```powershell
.\tasks.ps1 <command> -Profile <local|container|industrial|gpu>
```

---

## Campaigns Workflow

### Smoke (Quick Validation)

Validates that the environment and all experiment components are functional:

```powershell
.\tasks.ps1 smoke -Profile local
```

**Duration:** ~2 minutes | **Trials:** 1 | **Output:** Pass/fail status only

### Quick Campaign (Single Trial)

Runs the full experimental pipeline with a single trial per treatment for rapid iteration:

```powershell
# Security campaign (RQ1, RQ2, RQ3)
.\tasks.ps1 security-campaign -Profile local -Quick

# Availability campaign (RQ4)
.\tasks.ps1 availability-campaign -Profile local -Quick

# Analyze results and compute metrics
.\tasks.ps1 analyze -Profile local -Quick

# Generate publication-ready tables and figures
.\tasks.ps1 publication-artifacts -Profile local -Quick
```

**Trials:** 1 | **Output:** Full results structure

### Full Campaign (30 Trials)

Runs the complete experimental design with 30 independent trials for statistical validity:

```powershell
# Security campaign (RQ1, RQ2, RQ3)
.\tasks.ps1 security-campaign -Profile local

# Availability campaign (RQ4)
.\tasks.ps1 availability-campaign -Profile local

# Analyze results and compute metrics
.\tasks.ps1 analyze -Profile local

# Generate publication-ready tables and figures
.\tasks.ps1 publication-artifacts -Profile local
```

**Trials:** 30 | **Output:** Publication-ready artifacts

### GPU Campaign (RQ4 — NVIDIA L4)

The GPU campaign produces publication-quality RQ4 evidence with real CUDA inference
and NVML telemetry. It must be executed on a node with a GPU matching the profile
in `config/profiles/gpu.yaml`.

```bash
# Quick validation (3 trials, ~5–15 min)
python -m traceai rq4-campaign \
  --profile gpu \
  --quick \
  --mode experimental
```

Only after all quick validation gates pass:

```bash
# Full publication campaign (30 trials)
python -m traceai rq4-campaign \
  --profile gpu \
  --mode experimental
```

See [docs/GPU_CAMPAIGN_NVIDIA_L4.md](docs/GPU_CAMPAIGN_NVIDIA_L4.md) for the complete runbook.

---

## Result Directory Structure

After running campaigns, results are organized as follows:

```
traceai-ladc2026/
├── results/
│   ├── raw/                  # Unprocessed experiment outputs
│   │   ├── rq1/             # BOM coverage measurements
│   │   ├── rq2/             # Attestation gate logs
│   │   ├── rq3/             # VEX triage results
│   │   └── rq4/             # Runtime overhead & fault-injection logs
│   ├── normalized/           # Cleaned and structured data (CSV/JSON)
│   ├── summary/              # Aggregated statistics and hypothesis tests
│   └── public/               # Publication-ready tables, figures, and LaTeX snippets
└── generated/
    ├── boms/                 # Generated CycloneDX AI/ML-BOMs
    ├── attestations/         # Signed attestation bundles
    ├── vex/                  # VEX documents
    └── reports/              # Human-readable HTML/PDF reports
```

| Directory | Contents | Committed to Git? |
|-----------|----------|-------------------|
| `results/raw/` | Per-trial JSON logs, timing data, scanner output | No (`.gitignore`) |
| `results/normalized/` | Aggregated CSVs with trial ID, treatment, metrics | No |
| `results/summary/` | Descriptive stats, confidence intervals, effect sizes | No |
| `results/public/` | LaTeX tables, PDF figures, camera-ready snippets | Yes |
| `generated/` | BOMs, attestations, VEX docs, reports | No |

> **Note:** Run `.\tasks.ps1 analyze` to transform `raw/` → `normalized/` → `summary/` → `public/`.

---

## Troubleshooting

### PowerShell Execution Policy

**Symptom:** `File cannot be loaded because running scripts is disabled on this system.`

**Fix:**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

This sets the policy for the current session only and does not require administrator privileges.

---

### Missing Python

**Symptom:** `python : The term 'python' is not recognized...`

**Fix:** Install Python 3.11+ from [python.org](https://www.python.org/downloads/). Ensure "Add Python to PATH" is checked during installation. Restart your terminal after installation.

```powershell
python --version  # Should show Python 3.11.x or newer
```

---

### Missing GPU (Optional for local profile)

**Symptom:** `WARNING: No CUDA-capable GPU detected. Falling back to CPU.`

**Impact:** Local-profile experiments will run on CPU. This is supported for development and RQ1–RQ3 campaigns. CPU fallback is **not** permitted for the `gpu` profile (RQ4 publication evidence).

**Fix:** This is informational for the local profile. To enable GPU acceleration, install:
1. NVIDIA driver (latest Game Ready or Studio)
2. CUDA Toolkit 12.x+
3. PyTorch with CUDA support (select correct wheel from [pytorch.org](https://pytorch.org/get-started/locally/))

---

### CUDA/PyTorch Mismatch

**Symptom:** `RuntimeError: CUDA error: no kernel image is available for execution on the device`

**Fix:** Ensure your PyTorch CUDA version matches your installed CUDA Toolkit:

```powershell
python -c "import torch; print(torch.version.cuda)"  # Check PyTorch CUDA version
nvidia-smi                                             # Check driver CUDA version
```

Reinstall PyTorch with the correct CUDA version if they differ:
```powershell
# Select the correct wheel from https://pytorch.org/get-started/locally/
pip install torch --index-url https://download.pytorch.org/whl/<cuXXX>
```

---

### Hugging Face Download Errors

**Symptom:** `ConnectionError` or `HTTPError` when downloading GPT-2 weights.

**Fix:**
1. Check internet connectivity.
2. If behind a corporate proxy, set environment variables:
   ```powershell
   $env:HTTP_PROXY = "http://proxy:port"
   $env:HTTPS_PROXY = "http://proxy:port"
   ```
3. For persistent download issues, manually download and cache:
   ```powershell
   python -c "from transformers import AutoModel; AutoModel.from_pretrained('gpt2')"
   ```

---

### Windows Path Length

**Symptom:** `FileNotFoundError` or `OSError` with long nested paths.

**Fix:** Enable long path support (requires administrator, one-time):
```powershell
# Run as Administrator
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
    -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

Alternatively, clone the repository to a shorter base path (e.g., `C:\work\traceai`).

---

### Missing External Tools (Container/Industrial Profiles)

**Symptom:** `doctor` reports missing tools like `docker`, `cosign`, `syft`, or `grype`.

**Fix:** These tools are only required for the `container` and `industrial` profiles. The `local` profile works without them.

| Tool | Install |
|------|---------|
| Docker | [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/) |
| cosign | `go install github.com/sigstore/cosign/v2/cmd/cosign@latest` or [GitHub Releases](https://github.com/sigstore/cosign/releases) |
| syft | `choco install syft` or [GitHub Releases](https://github.com/anchore/syft/releases) |
| grype | `choco install grype` or [GitHub Releases](https://github.com/anchore/grype/releases) |

---

## Project Structure

```
traceai-ladc2026/
├── .github/                  # CI workflows
├── .venv/                    # Python virtual environment (generated)
├── config/
│   ├── profiles/
│   │   ├── local.yaml        # Local profile configuration
│   │   ├── container.yaml    # Container profile configuration
│   │   └── industrial.yaml   # Industrial profile configuration
│   ├── ground-truth/         # Curated dependency graphs (RQ1)
│   └── vex-templates/        # VEX document templates (RQ3)
├── fixtures/
│   ├── models/               # Cached model weights (GPT-2)
│   ├── datasets/             # Synthetic evaluation datasets
│   └── sboms/                # Reference BOM fixtures
├── generated/                # Runtime-generated artifacts (gitignored)
├── results/                  # Experiment outputs (gitignored except public/)
├── src/
│   ├── traceai/
│   │   ├── bom/              # BOM generation and validation (RQ1)
│   │   ├── attestation/      # Cryptographic signing and gates (RQ2)
│   │   ├── vex/              # VEX generation and triage (RQ3)
│   │   ├── runtime/          # Runtime guards and fault injection (RQ4)
│   │   ├── pipeline/         # LLM inference pipeline orchestration
│   │   └── analysis/         # Statistical analysis and reporting
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── campaigns/        # Campaign orchestration tests
├── tasks.ps1                 # PowerShell task runner (main entry point)
├── pyproject.toml            # Python project metadata and dependencies
├── requirements.lock         # Pinned dependency versions
├── LICENSE                   # MIT License
└── README.md                 # This file
```

---

## License

This project is licensed under the **MIT License**. See [LICENSE](LICENSE) for details.

```
MIT License

Copyright (c) 2026 TraceAI Authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Citation

If you use this work in your research, please cite:

```bibtex
@inproceedings{traceai2026ladc,
  title     = {From Static {AI/ML-BOMs} to Runtime-Aware Assurance: An Industrial Experience with {CycloneDX} for Dependable {LLM} Pipelines},
  author    = {Lima, Leonardo and others},
  booktitle = {Proceedings of the Latin-American Dependable Computing Conference (LADC)},
  year      = {2026},
  note      = {Replication package: \url{https://github.com/leolima/traceai-ladc2026}}
}
```

---

<p align="center">
  <em>TraceAI — Bridging the gap between static supply-chain metadata and runtime dependability assurance for AI/ML systems.</em>
</p>
