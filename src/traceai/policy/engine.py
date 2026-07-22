"""Fail-closed policy engine for deployment gates."""

import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

from traceai.logging_config import get_logger
from traceai.models import GateDecision
from traceai.settings import load_policy_config

logger = get_logger("policy.engine")


class PolicyEvaluation:
    """Result of a policy evaluation."""

    def __init__(self):
        self.decision: GateDecision = GateDecision.APPROVED
        self.checks_passed: list[str] = []
        self.checks_failed: list[str] = []
        self.reason: str = ""
        self.latency_ms: float = 0.0

    @property
    def approved(self) -> bool:
        return self.decision == GateDecision.APPROVED

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "approved": self.approved,
            "reason": self.reason,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "latency_ms": self.latency_ms,
        }


class PolicyEngine:
    """Fail-closed policy engine.

    Evaluates deployment artifacts against configured policy rules.
    On ANY invalid, missing, or unverifiable input, the gate DENIES.
    """

    def __init__(self, policy_config: Optional[dict] = None):
        if policy_config is None:
            try:
                full_config = load_policy_config()
                policy_config = full_config.get("policy", {})
            except FileNotFoundError:
                policy_config = {}

        self.config = policy_config
        self.mode = policy_config.get("mode", "fail-closed")

    def evaluate(
        self,
        artifact_present: bool = False,
        digest_match: bool = False,
        signature_valid: bool = False,
        signer_authorized: bool = False,
        attestation_valid: bool = False,
        attestation_digest_match: bool = False,
        evidence_fresh: bool = False,
        vex_valid: Optional[bool] = None,
        vulnerabilities_acceptable: bool = True,
        configuration_matches: bool = True,
    ) -> PolicyEvaluation:
        """Evaluate all policy checks and return a decision.

        Fail-closed: any failed check results in denial.
        """
        start = time.time()
        evaluation = PolicyEvaluation()

        checks = [
            ("artifact_present", artifact_present, GateDecision.MISSING_ARTIFACT),
            ("digest_match", digest_match, GateDecision.DIGEST_MISMATCH),
            ("signature_valid", signature_valid, GateDecision.INVALID_SIGNATURE),
            ("signer_authorized", signer_authorized, GateDecision.UNAUTHORIZED_SIGNER),
            ("attestation_valid", attestation_valid, GateDecision.MISSING_ATTESTATION),
            ("attestation_digest_match", attestation_digest_match, GateDecision.ATTESTATION_DIGEST_MISMATCH),
            ("evidence_fresh", evidence_fresh, GateDecision.STALE_EVIDENCE),
            ("configuration_matches", configuration_matches, GateDecision.CONFIGURATION_DRIFT),
        ]

        # VEX is optional but if provided must be valid
        if vex_valid is not None:
            checks.append(("vex_valid", vex_valid, GateDecision.VEX_MALFORMED))

        if not vulnerabilities_acceptable:
            checks.append(("vulnerabilities_acceptable", False, GateDecision.CRITICAL_VULNERABILITY))

        # Evaluate all checks - first failure determines decision
        for check_name, check_result, failure_decision in checks:
            if check_result:
                evaluation.checks_passed.append(check_name)
            else:
                evaluation.checks_failed.append(check_name)
                if evaluation.decision == GateDecision.APPROVED:
                    # First failure
                    evaluation.decision = failure_decision
                    evaluation.reason = f"Policy check failed: {check_name}"

        if evaluation.decision == GateDecision.APPROVED:
            evaluation.reason = "All policy checks passed"

        evaluation.latency_ms = (time.time() - start) * 1000
        return evaluation

    def evaluate_vex(
        self,
        vex_document: Optional[dict] = None,
        vex_signed: bool = False,
        vex_expired: bool = False,
        vex_component_match: bool = True,
        vex_schema_valid: bool = True,
    ) -> PolicyEvaluation:
        """Evaluate VEX-specific policy.

        The policy rejects:
        - Malformed VEX (invalid schema)
        - Expired VEX
        - VEX linked to wrong component
        - Unsigned VEX when signing is required
        """
        start = time.time()
        evaluation = PolicyEvaluation()
        vex_policy = self.config.get("vulnerability", {}).get("vex_policy", {})

        if vex_document is None:
            evaluation.decision = GateDecision.VEX_MALFORMED
            evaluation.reason = "No VEX document provided"
            evaluation.latency_ms = (time.time() - start) * 1000
            return evaluation

        # Schema validation
        if not vex_schema_valid:
            evaluation.decision = GateDecision.VEX_MALFORMED
            evaluation.reason = "VEX document fails schema validation"
            evaluation.checks_failed.append("vex_schema_valid")
            evaluation.latency_ms = (time.time() - start) * 1000
            return evaluation
        evaluation.checks_passed.append("vex_schema_valid")

        # Expiry check
        if vex_expired and vex_policy.get("reject_expired", True):
            evaluation.decision = GateDecision.VEX_EXPIRED
            evaluation.reason = "VEX document has expired"
            evaluation.checks_failed.append("vex_not_expired")
            evaluation.latency_ms = (time.time() - start) * 1000
            return evaluation
        evaluation.checks_passed.append("vex_not_expired")

        # Component linkage
        if not vex_component_match and vex_policy.get("reject_wrong_component", True):
            evaluation.decision = GateDecision.VEX_WRONG_COMPONENT
            evaluation.reason = "VEX linked to wrong component"
            evaluation.checks_failed.append("vex_component_match")
            evaluation.latency_ms = (time.time() - start) * 1000
            return evaluation
        evaluation.checks_passed.append("vex_component_match")

        # Signature requirement
        if vex_policy.get("require_signature", False) and not vex_signed:
            evaluation.decision = GateDecision.VEX_UNSIGNED
            evaluation.reason = "VEX document is unsigned (signing required)"
            evaluation.checks_failed.append("vex_signed")
            evaluation.latency_ms = (time.time() - start) * 1000
            return evaluation
        evaluation.checks_passed.append("vex_signed_or_not_required")

        evaluation.decision = GateDecision.APPROVED
        evaluation.reason = "VEX document passes all policy checks"
        evaluation.latency_ms = (time.time() - start) * 1000
        return evaluation

    def check_configuration_drift(
        self,
        approved_digest: str,
        current_digest: str,
    ) -> PolicyEvaluation:
        """Check for configuration drift between approved and current state."""
        start = time.time()
        evaluation = PolicyEvaluation()

        provenance = self.config.get("runtime", {})
        if not provenance.get("verify_configuration_digest", True):
            evaluation.decision = GateDecision.APPROVED
            evaluation.reason = "Configuration verification disabled"
            evaluation.latency_ms = (time.time() - start) * 1000
            return evaluation

        if approved_digest != current_digest:
            evaluation.decision = GateDecision.CONFIGURATION_DRIFT
            evaluation.reason = (
                f"Configuration drift detected: "
                f"approved={approved_digest[:16]}... current={current_digest[:16]}..."
            )
            evaluation.checks_failed.append("configuration_digest_match")
        else:
            evaluation.decision = GateDecision.APPROVED
            evaluation.reason = "Configuration matches approved state"
            evaluation.checks_passed.append("configuration_digest_match")

        evaluation.latency_ms = (time.time() - start) * 1000
        return evaluation
