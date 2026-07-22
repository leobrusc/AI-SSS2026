# Approved Fixtures

This directory holds **approved/baseline artifacts** used for testing in the TraceAI LADC 2026 pipeline.

## Purpose

Files in this directory represent known-good, verified artifacts that serve as the ground truth for integrity checks, reproducibility tests, and regression testing.

## Contents

- Model weight checksums (golden references)
- Validated SBOM/VEX documents
- Baseline inference outputs for deterministic prompts
- Approved configuration snapshots

## Usage

Tests compare runtime artifacts against these approved baselines to detect:
- Unintended model weight modifications
- SBOM/VEX document tampering
- Configuration drift
- Output regression

## Updating Baselines

When intentional changes are made, update baselines by running:
```bash
python scripts/update_baselines.py --source workspace/ --dest fixtures/approved/
```

All baseline updates must be reviewed and committed explicitly.
