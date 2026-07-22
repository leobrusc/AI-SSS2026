# Tampered Fixtures

This directory holds **tampered copies** of artifacts used for **fault injection** testing.

## Purpose

These files are intentionally modified versions of the approved baselines. They simulate various supply-chain attacks and integrity violations to verify that the TraceAI detection pipeline correctly identifies tampering.

## Tampering Scenarios

- **Bit-flip attacks**: Single-bit modifications in model weights
- **Metadata injection**: Altered SBOM/VEX metadata fields
- **Truncation**: Files with missing trailing bytes
- **Substitution**: Components replaced with different versions
- **Timestamp manipulation**: Backdated or future-dated signatures

## Usage

Fault injection tests load artifacts from this directory and verify that:
1. Integrity checks detect the modification
2. Alerts are raised with correct severity
3. The pipeline halts or quarantines the affected artifact

## Important

⚠️ **Do NOT use these files in production or for actual inference.**
They exist solely for testing detection mechanisms.

## Generating Tampered Files

```bash
python scripts/generate_tampered.py --source fixtures/approved/ --dest fixtures/tampered/
```
