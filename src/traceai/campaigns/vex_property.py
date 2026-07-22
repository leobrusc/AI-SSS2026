"""VEX property-based testing using Hypothesis.

Layer B: Generates reproducible VEX cases and validates against
an independent decision oracle (explicit decision table).
"""

import csv
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from traceai.logging_config import get_logger
from traceai.models import GateDecision
from traceai.policy.engine import PolicyEngine

logger = get_logger("campaigns.vex_property")

# Independent decision oracle — explicit truth table
# Priority order matches implementation: schema → expiry → component → signature
DECISION_TABLE = {
    # (schema_valid, expired, component_match, signed_when_required) -> decision
    (True, False, True, True): GateDecision.APPROVED,
    (True, False, True, False): GateDecision.VEX_UNSIGNED,
    (True, False, False, True): GateDecision.VEX_WRONG_COMPONENT,
    (True, False, False, False): GateDecision.VEX_WRONG_COMPONENT,
    (True, True, True, True): GateDecision.VEX_EXPIRED,
    (True, True, True, False): GateDecision.VEX_EXPIRED,
    (True, True, False, True): GateDecision.VEX_EXPIRED,  # expired checked before component
    (True, True, False, False): GateDecision.VEX_EXPIRED,
    (False, False, True, True): GateDecision.VEX_MALFORMED,
    (False, False, True, False): GateDecision.VEX_MALFORMED,
    (False, False, False, True): GateDecision.VEX_MALFORMED,
    (False, False, False, False): GateDecision.VEX_MALFORMED,
    (False, True, True, True): GateDecision.VEX_MALFORMED,
    (False, True, True, False): GateDecision.VEX_MALFORMED,
    (False, True, False, True): GateDecision.VEX_MALFORMED,
    (False, True, False, False): GateDecision.VEX_MALFORMED,
}


def oracle_decision(schema_valid: bool, expired: bool,
                    component_match: bool, signed_when_required: bool) -> GateDecision:
    """Independent oracle: determine expected decision from truth table."""
    key = (schema_valid, expired, component_match, signed_when_required)
    return DECISION_TABLE.get(key, GateDecision.VEX_MALFORMED)


def run_vex_property_tests(n_cases: int = 500, seed: int = 42,
                           require_signing: bool = False) -> dict:
    """Run property-based VEX tests with deterministic generation.

    Uses a simple PRNG-based generator (not Hypothesis) for full
    reproducibility without test-framework dependency at runtime.
    """
    import random
    rng = random.Random(seed)

    policy_config = {
        "vulnerability": {
            "vex_policy": {
                "require_signature": require_signing,
                "reject_expired": True,
                "reject_wrong_component": True,
                "require_valid_schema": True,
            }
        }
    }
    policy = PolicyEngine(policy_config)

    cases = []
    agreements = 0
    counterexamples = []

    for i in range(n_cases):
        # Generate random VEX parameters
        schema_valid = rng.random() > 0.15  # 85% valid schema
        expired = rng.random() > 0.75  # 25% expired
        component_match = rng.random() > 0.2  # 80% correct component
        is_signed = rng.random() > 0.3  # 70% signed
        signed_when_required = is_signed or not require_signing

        # Oracle decision (independent of implementation)
        expected = oracle_decision(schema_valid, expired, component_match, signed_when_required)

        # Implementation decision
        evaluation = policy.evaluate_vex(
            vex_document={"bomFormat": "CycloneDX"} if schema_valid else {"invalid": True},
            vex_signed=is_signed,
            vex_expired=expired,
            vex_component_match=component_match,
            vex_schema_valid=schema_valid,
        )
        observed = evaluation.decision

        agrees = (expected == observed)
        if agrees:
            agreements += 1
        else:
            counterexamples.append({
                "case": i,
                "params": {
                    "schema_valid": schema_valid,
                    "expired": expired,
                    "component_match": component_match,
                    "signed": is_signed,
                    "signed_when_required": signed_when_required,
                },
                "expected": expected.value,
                "observed": observed.value,
            })

        cases.append({
            "case_id": i,
            "schema_valid": schema_valid,
            "expired": expired,
            "component_match": component_match,
            "signed": is_signed,
            "expected_decision": expected.value,
            "observed_decision": observed.value,
            "agrees": agrees,
        })

    return {
        "total_cases": n_cases,
        "seed": seed,
        "require_signing": require_signing,
        "agreements": agreements,
        "agreement_rate": round(agreements / n_cases, 4) if n_cases > 0 else 0,
        "counterexamples": counterexamples,
        "counterexample_count": len(counterexamples),
        "cases": cases,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def save_vex_property_results(results: dict, output_dir: Path) -> None:
    """Save property-based VEX test results."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Cases CSV
    csv_path = output_dir / "vex_property_cases.csv"
    if results["cases"]:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=results["cases"][0].keys())
            w.writeheader()
            w.writerows(results["cases"])

    # Decision table JSON
    table_path = output_dir / "vex_decision_table.json"
    table_data = {
        "description": "Independent VEX decision oracle truth table",
        "columns": ["schema_valid", "expired", "component_match", "signed_when_required"],
        "decisions": {str(k): v.value for k, v in DECISION_TABLE.items()},
    }
    with open(table_path, "w", encoding="utf-8") as f:
        json.dump(table_data, f, indent=2)

    # Property results LaTeX
    tex_lines = [
        r"\begin{table}[htbp]",
        r"\caption{VEX Property-Based Test Results}",
        r"\label{tab:vex-property}",
        r"\centering\small",
        r"\begin{tabular}{lr}",
        r"\toprule",
        r"\textbf{Metric} & \textbf{Value} \\",
        r"\midrule",
        f"  Cases generated & {results['total_cases']} \\\\",
        f"  Seed & {results['seed']} \\\\",
        f"  Agreement rate & {results['agreement_rate']} \\\\",
        f"  Counterexamples & {results['counterexample_count']} \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    (output_dir / "vex_property_results.tex").write_text(
        "\n".join(tex_lines), encoding="utf-8")
