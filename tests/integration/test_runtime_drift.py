"""Integration tests for runtime configuration drift detection."""

import pytest

from traceai.hashing import hash_json
from traceai.models import GateDecision
from traceai.policy.engine import PolicyEngine

pytestmark = pytest.mark.integration


class TestRuntimeDrift:
    """Integration tests for configuration drift detection via PolicyEngine."""

    def test_configuration_drift_detected(self):
        """PolicyEngine detects drift when approved and current config digests differ."""
        # Simulate approved configuration
        approved_config = {
            "model_id": "openai-community/gpt2",
            "max_new_tokens": 100,
            "timeout_seconds": 30.0,
            "max_concurrency": 4,
        }
        approved_digest = hash_json(approved_config)

        # Simulate drifted configuration (someone changed max_concurrency)
        drifted_config = {
            "model_id": "openai-community/gpt2",
            "max_new_tokens": 100,
            "timeout_seconds": 30.0,
            "max_concurrency": 8,  # changed!
        }
        current_digest = hash_json(drifted_config)

        # Verify digests differ
        assert approved_digest != current_digest

        # PolicyEngine should detect drift
        engine = PolicyEngine(policy_config={
            "mode": "fail-closed",
            "runtime": {
                "verify_configuration_digest": True,
            },
        })

        result = engine.check_configuration_drift(
            approved_digest=approved_digest,
            current_digest=current_digest,
        )

        assert result.approved is False
        assert result.decision == GateDecision.CONFIGURATION_DRIFT
        assert "configuration_digest_match" in result.checks_failed

    def test_no_drift_when_config_unchanged(self):
        """PolicyEngine approves when approved and current digests match."""
        config = {
            "model_id": "openai-community/gpt2",
            "max_new_tokens": 100,
            "timeout_seconds": 30.0,
        }
        digest = hash_json(config)

        engine = PolicyEngine(policy_config={
            "mode": "fail-closed",
            "runtime": {
                "verify_configuration_digest": True,
            },
        })

        result = engine.check_configuration_drift(
            approved_digest=digest,
            current_digest=digest,
        )

        assert result.approved is True
        assert result.decision == GateDecision.APPROVED
        assert "configuration_digest_match" in result.checks_passed
