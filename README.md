# AI-SSS 2026 reproducibility artifact

**Operational Assurance for Secure Generative AI Supply Chains with CycloneDX**

RQ1–RQ3 camera-ready evidence is prepared. **RQ4_STATUS=PENDING_A100_EXECUTION**.
The Python import package remains `traceai`. The A100 replaces the previously
planned L4; historical CPU campaigns and mocked tests provide no A100 results.

| Question | Scope | Evidence |
| --- | --- | --- |
| RQ1 | Inventory identity representation | New frozen CPU experiment: 20/30 applicable assets; supersedes unreconciled historical 93.1% |
| RQ2 | Integrity/provenance policy | Historical 240 decisions and separately labeled property extensions |
| RQ3 | Scanner agreement | Raw Trivy/Grype findings with explicit advisory alias normalization |
| RQ4 | Availability under C0–C3 runtime controls | Pending: 240 normal requests and 6 separate fault observations on A100 |

Publication evidence, limitations and original provenance paths are indexed in
[results/public/ai-sss2026](results/public/ai-sss2026/README.md).
Historical raw evidence is preserved byte for byte. Inventory representation is
not security coverage; the reviewer audits state the limits of each claim.

## One-command A100 execution

Prerequisites: Linux x86_64, glibc 2.28+, Bash, uv, internet access to PyPI/PyTorch/
Hugging Face, and an operational NVIDIA driver compatible with CUDA 12.9.
Use a machine exposing exactly one **NVIDIA A100-SXM4-80GB**.

```bash
git clone https://github.com/leobrusc/AI-SSS2026.git
cd AI-SSS2026
bash scripts/a100/run_all.sh
```

Alternatively extract the GitHub source ZIP/tar.gz for tag
`ai-sss2026-a100-benchmark-v1`, enter its folder and run the same Bash command.
No Git metadata is required. The runner verifies committed source hashes,
creates `.venv-a100` from Python 3.11 and `uv.lock`, caches the exact model
revision, checks real CUDA tensors/NVML and loaded parameter dtype/device,
executes RQ4, validates counts and telemetry, and packages evidence.

Return exactly the two files printed after **RETURN THESE TWO FILES**:

```text
traceai_a100_results_<campaign_id>.tar.gz
traceai_a100_results_<campaign_id>.tar.gz.sha256
```

Failed runs are packaged as `NOT_VALID_FOR_PUBLICATION`; return those diagnostics
too. See [the concise runbook](docs/A100_RQ4_RUNBOOK.md). Real returned evidence
requires independent audit before RQ4 can be marked complete.

## Local reproducibility

`pyproject.toml` and `uv.lock` are authoritative. Python 3.11 is the release target.
The lock selects torch 2.9.1 CPU on Windows AMD64 and cu129 on Linux x86_64.
Other platforms are outside this release's support scope.

```bash
uv sync --locked --extra dev
uv run --locked pytest
uv run --locked python scripts/a100/benchmark.py --dry-run
```

The dry run checks source/protocol without model download or inference. Bash
users may use `bash scripts/a100/run_all.sh --dry-run`. GPU tests skip on CPU.
The original Windows `.venv` is excluded and retained locally as a dependency
oracle. Migration checks use `.venv-uv`; set `UV_PROJECT_ENVIRONMENT=.venv-uv`
to use that clean environment. Do not copy a virtual environment to Linux.

Legacy requirements files, installation docs and L4 scripts remain historical
provenance; uv and the A100 runbook supersede their execution instructions.

## Scientific protocol

[src/traceai/campaigns/rq4.py](src/traceai/campaigns/rq4.py) defines the authoritative
C0–C3 values and paired workload: 3 trials/configuration, 20 requests/trial,
240 normal observations plus 6 separate faults. The existing fault procedure is
retained; counts that differ fail validation without padding or synthetic rows.
Model: `sshleifer/tiny-gpt2`, revision
`5f91d94bd9cd7190a9f3216ff93cd1dd95f2c7be`, actual CUDA float16 parameters.
Weights are downloaded into an ignored cache and never committed.

GPU and host/process telemetry must overlap recorded trials. Native
`circuit_half_open` events do not prove a distinct HALF_OPEN state. This campaign
does not establish matched control overhead or cross-GPU equivalence.

Frozen baseline: `bb2d9e4b4703b8f59dcd6ef563df374fcbe79720`.
Safety tag: `pre-a100-cleanup-20261022`.
See [the release report](reviewer_analysis/A100_BENCHMARK_RELEASE_REPORT.md)
for dependency, cleanup and local test results.

See [CITATION.cff](CITATION.cff) and [LICENSE](LICENSE).
Repository: <https://github.com/leobrusc/AI-SSS2026>.
