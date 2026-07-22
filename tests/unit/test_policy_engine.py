"""Unit tests for traceai.policy.engine.PolicyEngine."""

import pytest

from traceai.models import GateDecision
from traceai.policy.engine import PolicyEngine

pytestmark = pytest.mark.unit


class TestPolicyEngineEvaluate:
    """Tests for PolicyEngine.evaluate method."""

    def test_all_checks_pass(self, policy_engine):
        """When all checks pass, decision is APPROVED."""
        result = policy_engine.evaluate(
            artifact_present=True,
            digest_match=True,
            signature_valid=True,
            signer_authorized=True,
            attestation_valid=True,
            attestation_digest_match=True,
            evidence_fresh=True,
            vex_valid=True,
            vulnerabilities_acceptable=True,
            configuration_matches=True,
        )

        assert result.approved is True
        assert result.decision == GateDecision.APPROVED
        assert len(result.checks_failed) == 0

    def test_fail_closed_on_missing_artifact(self, policy_engine):
        """Missing artifact triggers MISSING_ARTIFACT decision."""
        result = policy_engine.evaluate(
            artifact_present=False,
            digest_match=True,
            signature_valid=True,
            signer_authorized=True,
            attestation_valid=True,
            attestation_digest_match=True,
            evidence_fresh=True,
        )

        assert result.approved is False
        assert result.decision == GateDecision.MISSING_ARTIFACT
        assert "artifact_present" in result.checks_failed

    def test_fail_closed_on_digest_mismatch(self, policy_engine):
        """Digest mismatch triggers DIGEST_MISMATCH decision."""
        result = policy_engine.evaluate(
            artifact_present=True,
            digest_match=False,
            signature_valid=True,
            signer_authorized=True,
            attestation_valid=True,
            attestation_digest_match=True,
            evidence_fresh=True,
        )

        assert result.approved is False
        assert result.decision == GateDecision.DIGEST_MISMATCH
        assert "digest_match" in result.checks_failed

    def test_fail_closed_on_invalid_signature(self, policy_engine):
        """Invalid signature triggers INVALID_SIGNATURE decision."""
        result = policy_engine.evaluate(
            artifact_present=True,
            digest_match=True,
            signature_valid=False,
            signer_authorized=True,
            attestation_valid=True,
            attestation_digest_match=True,
            evidence_fresh=True,
        )

        assert result.approved is False
        assert result.decision == GateDecision.INVALID_SIGNATURE
        assert "signature_valid" in result.checks_failed


class TestPolicyEngineVex:
    """Tests for PolicyEngine.evaluate_vex method."""

    def test_vex_valid_passes(self, policy_engine, sample_vex_valid):
        """Valid VEX document passes all checks."""
        result = policy_engine.evaluate_vex(
            vex_document=sample_vex_valid,
            vex_signed=False,
            vex_expired=False,
            vex_component_match=True,
            vex_schema_valid=True,
        )

        assert result.approved is True
        assert result.decision == GateDecision.APPROVED

    def test_vex_expired_rejected(self, policy_engine, sample_vex_valid):
        """Expired VEX document is rejected."""
        result = policy_engine.evaluate_vex(
            vex_document=sample_vex_valid,
            vex_signed=False,
            vex_expired=True,
            vex_component_match=True,
            vex_schema_valid=True,
        )

        assert result.approved is False
        assert result.decision == GateDecision.VEX_EXPIRED

    def test_vex_wrong_component_rejected(self, policy_engine, sample_vex_valid):
        """VEX linked to wrong component is rejected."""
        result = policy_engine.evaluate_vex(
            vex_document=sample_vex_valid,
            vex_signed=False,
            vex_expired=False,
            vex_component_match=False,
            vex_schema_valid=True,
        )

        assert result.approved is False
        assert result.decision == GateDecision.VEX_WRONG_COMPONENT

    def test_vex_malformed_rejected(self, policy_engine, sample_vex_malformed):
        """Malformed VEX (invalid schema) is rejected."""
        result = policy_engine.evaluate_vex(
            vex_document=sample_vex_malformed,
            vex_signed=False,
            vex_expired=False,
            vex_component_match=True,
            vex_schema_valid=False,
        )

        assert result.approved is False
        assert result.decision == GateDecision.VEX_MALFORMED


class TestPolicyEngineConfigurationDrift:
    """Tests for PolicyEngine.check_configuration_drift method."""

    def test_configuration_drift_detected(self, policy_engine):
        """Drift detected when approved and current digests differ."""
        result = policy_engine.check_configuration_drift(
            approved_digest="abc123" * 10,
            current_digest="def456" * 10,
        )

        assert result.approved is False
        assert result.decision == GateDecision.CONFIGURATION_DRIFT
        assert "configuration_digest_match" in result.checks_failed
