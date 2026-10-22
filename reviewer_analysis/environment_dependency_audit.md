# Environment dependency audit

Original Windows .venv retained as an oracle; never copied or committed.
Python 3.11.6; pip check: No broken requirements found. Full freeze and site-packages directory inventory are adjacent.
AST import evidence is in dependency_import_inventory.csv (src, scripts, tests, camera-ready adapters and audits).

Authoritative inputs: pyproject.toml + uv.lock. requirements.in/.txt are former broad runtime declarations; requirements-exact.txt and requirements.lock pin the old Windows CPU environment; requirements-dev.in includes legacy pip-tools. They remain unchanged historical provenance and are not used for this release.

torch 2.13.0+cpu in the oracle is replaced by required 2.9.1; Windows CPU and Linux cu129 are selected by uv markers. Transformers is constrained below 5 to use its established GPT2 loader with torch 2.9.1. tokenizers remains transitive. pandas has no imports in audited source and is removed from direct dependencies. pip-tools, torchvision and hypothesis are not required. GPU telemetry adds nvidia-ml-py, absent from the CPU oracle.

| Dependency | Oracle version | Classification | Import/use evidence |
|---|---|---|---|
| Jinja2 | 3.1.6 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| MarkupSafe | 3.0.3 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| PyYAML | 6.0.3 | CORE_RUNTIME | `scripts/phase5_gpu_runbook.py`, `src/traceai/logging_config.py`, `src/traceai/settings.py` |
| Pygments | 2.20.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| annotated-doc | 0.0.4 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| annotated-types | 0.7.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| anyio | 4.14.2 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| ast_serialize | 0.6.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| attrs | 26.1.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| build | 1.5.0 | LEGACY_UNUSED | No direct AST import; transitive/build/tool only |
| certifi | 2026.7.22 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| cffi | 2.1.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| click | 8.4.2 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| colorama | 0.4.6 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| contourpy | 1.3.3 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| coverage | 7.15.2 | DEV_TEST | No direct AST import; transitive/build/tool only |
| cryptography | 49.0.0 | CORE_RUNTIME | `reviewer_analysis/fresh_audit.py`, `reviewer_analysis/local_verifier_extension.py`, `src/traceai/provenance/signer.py` |
| cycler | 0.12.1 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| fastapi | 0.139.2 | CORE_RUNTIME | `src/traceai/service/app.py` |
| filelock | 3.29.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| fonttools | 4.63.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| fsspec | 2026.4.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| h11 | 0.16.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| hf-xet | 1.5.2 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| httpcore | 1.0.9 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| httptools | 0.8.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| httpx | 0.28.1 | RQ4_RUNTIME | `scripts/phase3_rq4_controls.py`, `scripts/phase4_rq4_cpu_diagnostic.py`, `src/traceai/campaigns/availability.py` |
| huggingface_hub | 1.24.0 | RQ4_RUNTIME | `scripts/a100/benchmark.py` |
| hypothesis | 6.160.0 | LEGACY_UNUSED | No direct AST import; transitive/build/tool only |
| idna | 3.18 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| iniconfig | 2.3.0 | DEV_TEST | No direct AST import; transitive/build/tool only |
| jsonschema | 4.26.0 | CORE_RUNTIME | `src/traceai/bom/validators.py` |
| jsonschema-specifications | 2025.9.1 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| kiwisolver | 1.5.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| librt | 0.13.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| markdown-it-py | 4.2.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| matplotlib | 3.11.1 | CORE_RUNTIME | `src/traceai/analysis/figures.py` |
| mdurl | 0.1.2 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| mpmath | 1.3.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| mypy | 2.3.0 | DEV_TEST | No direct AST import; transitive/build/tool only |
| mypy_extensions | 1.1.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| networkx | 3.6.1 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| numpy | 2.4.4 | CORE_RUNTIME | `reviewer_analysis/fresh_audit.py`, `reviewer_analysis/refine_audit.py`, `scripts/phase3_rq4_controls.py` |
| nvidia-ml-py | not installed | GPU_RUNTIME | `scripts/a100/benchmark.py`, `scripts/phase5_gpu_runbook.py`, `src/traceai/campaigns/rq4.py` |
| packaging | 26.2 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| pandas | 3.0.3 | LEGACY_UNUSED | No direct AST import; transitive/build/tool only |
| pathspec | 1.1.1 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| pillow | 12.2.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| pip-tools | 7.6.0 | LEGACY_UNUSED | No direct AST import; transitive/build/tool only |
| pluggy | 1.6.0 | DEV_TEST | No direct AST import; transitive/build/tool only |
| psutil | 7.2.2 | RQ4_RUNTIME | `reviewer_analysis/rq1_reconcile.py`, `scripts/a100/benchmark.py`, `src/traceai/campaigns/availability.py` |
| pycparser | 3.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| pydantic | 2.13.4 | CORE_RUNTIME | `src/traceai/models.py`, `src/traceai/service/app.py`, `src/traceai/settings.py` |
| pydantic-settings | 2.14.2 | CORE_RUNTIME | `src/traceai/settings.py` |
| pydantic_core | 2.46.4 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| pyparsing | 3.3.2 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| pyproject_hooks | 1.2.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| pytest | 9.1.1 | DEV_TEST | `tests/conftest.py`, `tests/integration/test_inference_smoke.py`, `tests/integration/test_runtime_drift.py` |
| pytest-asyncio | 1.4.0 | DEV_TEST | No direct AST import; transitive/build/tool only |
| pytest-cov | 7.1.0 | DEV_TEST | No direct AST import; transitive/build/tool only |
| python-dateutil | 2.9.0.post0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| python-dotenv | 1.2.2 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| referencing | 0.37.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| regex | 2026.7.19 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| rich | 15.0.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| rpds-py | 2026.6.3 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| ruff | 0.15.22 | DEV_TEST | No direct AST import; transitive/build/tool only |
| safetensors | 0.8.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| scipy | 1.17.1 | CORE_RUNTIME | `reviewer_analysis/compute_rq2.py`, `reviewer_analysis/fresh_audit.py`, `src/traceai/analysis/figures.py` |
| shellingham | 1.5.4 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| six | 1.17.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| sortedcontainers | 2.4.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| starlette | 1.3.1 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| sympy | 1.14.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| tokenizers | 0.22.2 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| torch | 2.13.0+cpu | RQ4_RUNTIME | `reviewer_analysis/l4_camera_ready_runner.py`, `scripts/a100/benchmark.py`, `scripts/phase5_gpu_runbook.py` |
| torchvision | 0.28.0+cpu | LEGACY_UNUSED | No direct AST import; transitive/build/tool only |
| tqdm | 4.69.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| transformers | 5.14.1 | RQ4_RUNTIME | `scripts/phase5_gpu_runbook.py`, `src/traceai/campaigns/rq1.py`, `src/traceai/campaigns/rq1_finalizer.py` |
| typer | 0.27.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| typing-inspection | 0.4.2 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| typing_extensions | 4.15.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| tzdata | 2026.3 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| uvicorn | 0.51.0 | CORE_RUNTIME | `src/traceai/service/app.py` |
| watchfiles | 1.2.0 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |
| websockets | 16.1.1 | TRANSITIVE_ONLY | No direct AST import; transitive/build/tool only |

Source guidance: [uv platform-specific indexes](https://docs.astral.sh/uv/concepts/indexes/); [official cu129 torch wheels](https://download.pytorch.org/whl/cu129/torch/). The actual uv resolver and sync validate syntax and availability.
