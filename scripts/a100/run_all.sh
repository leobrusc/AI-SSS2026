#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$ROOT/.venv-a100}"
if [[ "${1:-}" == "--dry-run" ]]; then
    command -v uv >/dev/null
    uv run --locked --python 3.11 python scripts/a100/benchmark.py --dry-run
    exit 0
fi
if [[ $# -gt 0 ]]; then echo 'Usage: bash scripts/a100/run_all.sh [--dry-run]' >&2; exit 2; fi
CAMPAIGN_ID="a100-$(date -u +%Y%m%dT%H%M%SZ)-$$"
OUT="results/camera_ready/a100/$CAMPAIGN_ID"
mkdir -p "$OUT"
finish() {
    rc=$?
    trap - EXIT
    if command -v uv >/dev/null; then
        uv run --no-project --python 3.11 python scripts/a100/package_results.py "$OUT" "$rc" || exit 1
    else
        echo "uv unavailable; diagnostics retained in $OUT. Install uv and retry." >&2
    fi
    exit "$rc"
}
trap finish EXIT
exec > >(tee "$OUT/console.log") 2>&1
cat benchmark-release.json
[[ "$(uname -s)" == "Linux" && "$(uname -m)" == "x86_64" ]] || { echo 'Requires Linux x86_64'; exit 1; }
command -v uv >/dev/null || { echo 'Install uv: https://docs.astral.sh/uv/getting-started/installation/'; exit 1; }
uv --version
export UV_PROJECT_ENVIRONMENT="$ROOT/.venv-a100"
unset VIRTUAL_ENV TRACEAI_MODEL_DIR
export HF_HOME="$ROOT/.hf-cache"
export TRACEAI_DEVICE=cuda
uv sync --locked --python 3.11 --no-dev
uv run --locked python scripts/a100/benchmark.py --output "$OUT"
