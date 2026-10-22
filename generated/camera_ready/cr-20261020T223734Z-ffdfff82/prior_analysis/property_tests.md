# Property-Based Tests

**Audit status:** OBSERVED FROM RAW DATA + INFERRED FROM CODE  
**Sources:** `src/traceai/campaigns/vex_property.py`,  
`generated/rq3/vex_property_cases.csv` (500 rows, OBSERVED),  
`generated/rq3/vex_decision_table.json` (OBSERVED)

---

## 1. Test Framework

**CRITICAL FINDING:** The module is documented as "VEX property-based testing using Hypothesis" (docstring in `vex_property.py`), but the implementation uses `random.Random(seed)`, **NOT** the Hypothesis library.

Source: `src/traceai/campaigns/vex_property.py`, function `run_vex_property_tests()`:
```python
import random
rng = random.Random(seed)
```

No `hypothesis` import exists in this file. The function signature comment explicitly states:
> "Uses a simple PRNG-based generator (not Hypothesis) for full reproducibility without test-framework dependency at runtime."

**Implication for paper:** The paper must not state that Hypothesis was used. The correct description is: "500 deterministic randomised test cases generated with `random.Random(seed=42)` against an independent decision oracle."

---

## 2. Test Configuration

| Property | Value | Source |
|----------|-------|--------|
| Total cases | 500 | OBSERVED — `vex_property_cases.csv` has 500 rows |
| Seed | 42 | INFERRED FROM CODE — `run_vex_property_tests(n_cases=500, seed=42)` |
| Framework | `random.Random` | INFERRED FROM CODE |
| Signing required | False (default) | INFERRED FROM CODE — `require_signing=False` |

---

## 3. Input Generators

Four Boolean input dimensions, each drawn from `rng.random()`:

| Parameter | Generation rule | Observed distribution (500 cases) |
|-----------|----------------|----------------------------------|
| `schema_valid` | `rng.random() > 0.15` → P(True)≈0.85 | True: 427 (85.4%), False: 73 (14.6%) |
| `expired` | `rng.random() > 0.75` → P(True)≈0.25 | True: 125 (25.0%), False: 375 (75.0%) |
| `component_match` | `rng.random() > 0.20` → P(True)≈0.80 | True: 408 (81.6%), False: 92 (18.4%) |
| `is_signed` | `rng.random() > 0.30` → P(True)≈0.70 | True: 357 (71.4%), False: 143 (28.6%) |

`signed_when_required` = `is_signed OR NOT require_signing`. With `require_signing=False`, `signed_when_required=True` for all cases.

---

## 4. Oracle

Source: `DECISION_TABLE` dict in `src/traceai/campaigns/vex_property.py` (16 entries)

| (schema_valid, expired, component_match, signed_when_required) | Expected decision |
|--------------------------------------------------------------|-----------------|
| (True, False, True, True) | APPROVED |
| (True, False, True, False) | VEX_UNSIGNED |
| (True, False, False, True) | VEX_WRONG_COMPONENT |
| (True, False, False, False) | VEX_WRONG_COMPONENT |
| (True, True, True, True) | VEX_EXPIRED |
| (True, True, True, False) | VEX_EXPIRED |
| (True, True, False, True) | VEX_EXPIRED (expiry checked before component) |
| (True, True, False, False) | VEX_EXPIRED |
| (False, *, *, *) — all 8 combinations | VEX_MALFORMED |

The oracle is hardcoded as an explicit lookup table, independent of the `PolicyEngine` implementation.

---

## 5. Decision Distribution (500 cases, OBSERVED)

| Decision | Expected count | Observed count | Match |
|---------|---------------|---------------|-------|
| APPROVED | 257 | 257 | ✓ |
| VEX_MALFORMED | 73 | 73 | ✓ |
| VEX_WRONG_COMPONENT | 60 | 60 | ✓ |
| VEX_EXPIRED | 110 | 110 | ✓ |
| VEX_UNSIGNED | 0 | 0 | ✓ (require_signing=False) |
| **Total** | **500** | **500** | ✓ |

---

## 6. Counterexamples

| Metric | Value | Source |
|--------|-------|--------|
| Agreements | 500 | OBSERVED from `vex_property_cases.csv` (all `agrees=True`) |
| Counterexamples | 0 | OBSERVED |
| Agreement rate | 1.0000 | OBSERVED |

---

## 7. Input Domain and Coverage

| Domain | Coverage notes |
|--------|--------------|
| Schema validity | Both valid (85%) and invalid (15%) |
| Expiry | Both expired (25%) and valid (75%) |
| Component linkage | Both matched (82%) and mismatched (18%) |
| Signing | Both signed (71%) and unsigned (29%) |
| Signing requirement | Only `require_signing=False` tested (signing requirement not exercised) |
| VEX_UNSIGNED path | NOT EXERCISED in this run (require_signing=False means signed_when_required=True always) |

**Gap:** The VEX_UNSIGNED decision path is defined in the oracle but never triggered in the 500-case run because `require_signing=False`. To cover the VEX_UNSIGNED path, a second run with `require_signing=True` would be needed.

---

## 8. Reconstructed Truth Table / Oracle

The oracle verifies the following behavioural properties of `PolicyEngine.evaluate_vex()`:

1. **Schema-first:** Invalid schema → MALFORMED regardless of all other inputs
2. **Expiry before linkage:** Expired VEX → EXPIRED even if component is wrong (temporal check takes priority)
3. **Linkage before signing:** Wrong component → WRONG_COMPONENT even if unsigned
4. **Approval only on all-pass:** APPROVED only when (schema_valid=True, expired=False, component_match=True, signed_when_required=True)

These 4 properties are validated exhaustively against all 500 randomly generated cases. Zero counterexamples confirm that the `PolicyEngine` implementation matches the oracle for all tested inputs.

---

## 9. Comparison with Unit Tests

The methodology tests in `tests/unit/test_methodology.py` also cover VEX oracle properties:
- `TestVexOracleIndependence` (from test file — observed in file listing)
- Tests use `pytest` and real `PolicyEngine` instantiation
- These are distinct from the 500-case property run (different framework, overlapping coverage)

The `tests/unit/test_vex.py` file (3378 bytes) contains targeted unit tests for VEX parsing.

---

## 10. Pass/Fail Summary

| Property | Value |
|---------|-------|
| All 500 cases pass | YES (OBSERVED) |
| Oracle is independent of implementation | YES — `DECISION_TABLE` is a separate dict not using `PolicyEngine` |
| Reproducible | YES — deterministic seed=42 |
| Counterexamples found | 0 (OBSERVED) |
| Hypothesis used | NO — `random.Random` only |
| VEX_UNSIGNED path covered | NO — requires `require_signing=True` |
