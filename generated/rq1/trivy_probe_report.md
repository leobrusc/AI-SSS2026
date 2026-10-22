# Trivy Python Detection Probe Report

**Trivy version:** 0.72.0  
**Corrected classification:** SUPPORTED_INPUT_FORMAT_MISMATCH

## Root Cause

The project requirements.txt uses >= version specifiers. Trivy pip scanner
requires exact == pins to resolve package versions. With requirements-exact.txt
(exact pins from pip freeze), Trivy discovers 23 components successfully.

## Probe Results

| Probe | Components | Classification |
|-------|-----------|----------------|
| Isolated fixture (==) | 6 | SUPPORTED_AND_DETECTED |
| JSON format | 5 | SUPPORTED_BUT_ZERO_VULNERABILITIES |
| Root with requirements-exact.txt | 23 | SUPPORTED_AND_DETECTED |

## Previous (Incorrect) Classification

TOOL_LIMITATION — This was incorrect. The tool works correctly when given
its expected input format (exact-pinned requirements.txt with == versions).
