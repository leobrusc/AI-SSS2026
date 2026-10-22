# VEX Policy Semantics

**Audit status:** INFERRED FROM CODE + OBSERVED FROM CAMPAIGNS  
**Sources:** `src/traceai/vulnerability/vex.py`, `src/traceai/policy/engine.py`,  
`config/policy.yaml`, `fixtures/vex/`, `results/rq3/rq3-20260722-140819-082e9531/vex_decisions.csv`

---

## 1. VEX Format

The implementation uses **CycloneDX VEX** (not CSAF/OpenVEX).

Required fields from `validate_vex_schema()` in `src/traceai/vulnerability/vex.py`:
- `bomFormat: "CycloneDX"` (must equal this exact string)
- `vulnerabilities[]` array
- Each vulnerability must have `id` and `analysis` fields

---

## 2. VEX Status Values

Source: `src/traceai/vulnerability/vex.py` (constants at module level)

| Constant | Value | Policy effect |
|---------|-------|--------------|
| VEX_STATUS_NOT_AFFECTED | `"not_affected"` | Vulnerability SUPPRESSED from actionable list |
| VEX_STATUS_AFFECTED | `"affected"` | Vulnerability RETAINED; workaround may be noted |
| VEX_STATUS_FIXED | `"fixed"` | Vulnerability RETAINED in list (policy treats as present) |
| VEX_STATUS_UNDER_INVESTIGATION | `"under_investigation"` | Vulnerability RETAINED |

Only `not_affected` suppresses a finding. All other statuses result in the vulnerability remaining in the actionable list.

Source: `apply_vex_to_findings()` in `vex.py`:
```python
if status == VEX_STATUS_NOT_AFFECTED:
    suppressed += 1
    ...
else:
    remaining.append(finding)
```

---

## 3. VEX Document Fields

Source: `VexDocument._parse()` in `src/traceai/vulnerability/vex.py`

| Field | Path in CycloneDX JSON | Implemented |
|-------|----------------------|------------|
| vulnerability ID | `vulnerabilities[].id` | YES |
| status | `vulnerabilities[].analysis.state` | YES |
| justification | `vulnerabilities[].analysis.justification` | YES (stored, not enforced) |
| detail | `vulnerabilities[].analysis.detail` | YES (stored, not enforced) |
| response | `vulnerabilities[].analysis.response[]` | YES (stored, not enforced) |
| affected component refs | `vulnerabilities[].affects[].ref` | YES |
| VEX metadata timestamp | `metadata.timestamp` | YES (for expiry check) |
| VEX owner/author | `metadata.component.name` | NOT_PARSED (not extracted in `_parse()`) |
| `issued_at` | NOT_PRESENT | Not in parsed fields |
| `valid_until` | via `metadata.properties[traceai:expires]` | YES (expiry check) |

**Note on `valid_until`:** Not a standard CycloneDX field. The expiry mechanism uses a custom property:
```json
{"name": "traceai:expires", "value": "2026-08-21T00:00:00Z"}
```
Standard CycloneDX does not define a validity period for VEX documents directly.

---

## 4. Policy Evaluation Order

Source: `src/traceai/policy/engine.py` → `evaluate_vex()`

```
1. vex_document is None?          → VEX_MALFORMED
2. vex_schema_valid = False?      → VEX_MALFORMED
3. vex_expired = True?            → VEX_EXPIRED   (checked BEFORE component linkage)
4. vex_component_match = False?   → VEX_WRONG_COMPONENT
5. vex_signed = False AND require_signature = True?  → VEX_UNSIGNED
6. All checks pass                → APPROVED
```

Priority order is **fail-fast**: first failure determines outcome. Expiry is checked before component linkage (important for edge cases).

---

## 5. Policy Configuration

Source: `config/policy.yaml` → `vulnerability.vex_policy`

| Setting | Value | Notes |
|---------|-------|-------|
| `accept_not_affected` | `true` | not_affected VEX suppresses finding |
| `require_valid_schema` | `true` | malformed VEX rejected |
| `require_signature` | `false` | VEX signing not required in local profile |
| `reject_expired` | `true` | Expired VEX is rejected |
| `reject_wrong_component` | `true` | Wrong component reference is rejected |
| `max_vex_age_hours` | `720` (30 days) | NOTE: This is not directly used by `evaluate_vex()`; the `vex_expired` boolean is computed by caller |

---

## 6. Validity Period and Expiration

Source: `src/traceai/vulnerability/vex.py` → `VexDocument.is_expired`

- Expiry is stored as `metadata.properties[name="traceai:expires"]`
- Checked by parsing the ISO datetime value and comparing to `datetime.now(timezone.utc)`
- `is_expired` is a property on `VexDocument`, not a gate-time check
- The caller must invoke `vex_doc.is_expired` and pass the result as `vex_expired` to `evaluate_vex()`

**Fixture evidence:** `fixtures/vex/expired.json` contains `"traceai:expires": "2020-01-01T00:00:00Z"` (OBSERVED: confirmed expired). `fixtures/vex/not_affected.valid.json` does not contain an expiry property (no expiry → `is_expired=False`).

---

## 7. Ownership and `issued_at`

| Field | Status |
|-------|--------|
| `owner` | NOT_IMPLEMENTED — not extracted or enforced |
| `issued_at` | NOT_IMPLEMENTED — `metadata.timestamp` is present in CycloneDX but not explicitly parsed or stored as `issued_at` |
| Multi-owner / multi-VEX conflicts | NOT_IMPLEMENTED — no conflict resolution logic |
| VEX precedence rules | NOT_IMPLEMENTED — if multiple VEX documents cover the same CVE, the last one applied wins (list order) |

---

## 8. Fail-Open vs Fail-Closed

**Behavior: FAIL-CLOSED for invalid/expired/wrong-component VEX.**

- Malformed VEX → gate returns `VEX_MALFORMED` → deny
- Expired VEX → gate returns `VEX_EXPIRED` → deny
- Wrong-component VEX → gate returns `VEX_WRONG_COMPONENT` → deny
- VEX unsigned when required → `VEX_UNSIGNED` → deny
- No VEX document provided → `VEX_MALFORMED` → deny

**EXCEPTION:** If `vex_valid=None` is passed to `PolicyEngine.evaluate()` (i.e., VEX is not evaluated), no VEX check is performed. This is used in scenarios where VEX is not applicable (e.g., when no vulnerability scan is run). This could be interpreted as fail-open for the VEX sub-check specifically.

---

## 9. Stale VEX Behavior

Source: `config/policy.yaml` → `max_vex_age_hours: 720`

- 30-day maximum VEX age defined in policy configuration
- However, this value is NOT directly enforced in `evaluate_vex()` — the method receives a pre-computed `vex_expired: bool` from the caller
- The caller computes `vex_expired` from `VexDocument.is_expired` which uses the `traceai:expires` custom property
- If `traceai:expires` is absent, `is_expired` returns `False` (NOT expired) regardless of `max_vex_age_hours`
- This means the 30-day limit from policy.yaml is effectively advisory — it is not automatically applied

**Gap:** The policy setting `max_vex_age_hours=720` is defined but not wired into the validation logic. A VEX document without a `traceai:expires` property will never be flagged as stale.

---

## 10. Conflicts and Precedence

| Scenario | Behavior | Status |
|---------|---------|--------|
| Two VEX docs cover same CVE, one says not_affected, one says affected | `apply_vex_to_findings()` iterates through statements; last match wins | IMPLEMENTED (last-wins) |
| VEX from different sources | No source validation | NOT_IMPLEMENTED |
| VEX for non-scanned component | VEX suppresses nothing (no matching finding) | IMPLEMENTED correctly |
| VEX with future `issued_at` | Not checked | NOT_IMPLEMENTED |

---

## 11. Evidence References

| Field | In VEX | Tracked |
|-------|--------|---------|
| `evidence_ref` (cross-reference to finding) | Not a standard CycloneDX VEX field; uses `affects[].ref` → bom-ref | PARTIALLY |
| `analysis.justification` | YES — stored in parsed statement | YES (stored) |
| `analysis.detail` | YES | YES (stored) |
| `analysis.response` | YES | YES (stored) |
| External advisory URL | Not extracted | NOT_IMPLEMENTED |
