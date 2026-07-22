"""Integration tests for tamper detection through the deployment gate."""

import os
from pathlib import Path

import pytest

from traceai.hashing import hash_file
from traceai.models import GateDecision
from traceai.policy.engine import PolicyEngine
from traceai.provenance.verifier import create_verifier

pytestmark = pytest.mark.integration


class TestTamperGate:
    """Integration tests verifying the signer/verifier/gate pipeline."""

    def test_approved_deployment_passes(self, local_signer, tmp_path):
        """An artifact signed by an authorized signer passes the gate."""
        # Create a model artifact
        model_file = tmp_path / "model.safetensors"
        model_file.write_bytes(os.urandom(2048))
        model_digest = hash_file(model_file)

        # Sign the attestation payload
        attestation_payload = {
            "model_id": "test-model",
            "model_digest": model_digest,
            "profile": "local",
        }
        envelope = local_signer.sign_json(attestation_payload)

        # Verify with authorized signer
        fingerprint = local_signer.get_fingerprint()
        verifier = create_verifier(
            allowed_fingerprints=[fingerprint],
            max_evidence_age_hours=24,
        )
        ver_result = verifier.verify_signature(
            envelope, local_signer.get_public_key_pem()
        )

        assert ver_result.approved is True
        assert ver_result.decision == GateDecision.APPROVED

        # Full gate evaluation should pass
        engine = PolicyEngine(policy_config={"mode": "fail-closed"})
        gate_result = engine.evaluate(
            artifact_present=True,
            digest_match=True,
            signature_valid=True,
            signer_authorized=True,
            attestation_valid=True,
            attestation_digest_match=True,
            evidence_fresh=True,
            configuration_matches=True,
        )

        assert gate_result.approved is True

    def test_tampered_model_detected(self, local_signer, tmp_path):
        """A tampered model triggers digest mismatch in the gate."""
        # Create and sign the original model
        model_file = tmp_path / "model.safetensors"
        original_data = os.urandom(2048)
        model_file.write_bytes(original_data)
        original_digest = hash_file(model_file)

        # Tamper the model
        tampered_data = bytearray(original_data)
        tampered_data[0] = (tampered_data[0] + 1) % 256
        model_file.write_bytes(bytes(tampered_data))
        tampered_digest = hash_file(model_file)

        # Digests should differ
        assert original_digest != tampered_digest

        # Verify digest mismatch
        verifier = create_verifier()
        digest_result = verifier.verify_digest_match(
            attested_digest=original_digest,
            observed_digest=tampered_digest,
            artifact_name="model",
        )

        assert digest_result.approved is False
        assert digest_result.decision == GateDecision.DIGEST_MISMATCH

        # Gate evaluation rejects
        engine = PolicyEngine(policy_config={"mode": "fail-closed"})
        gate_result = engine.evaluate(
            artifact_present=True,
            digest_match=False,
            signature_valid=True,
            signer_authorized=True,
            attestation_valid=True,
            attestation_digest_match=True,
            evidence_fresh=True,
            configuration_matches=True,
        )

        assert gate_result.approved is False
        assert gate_result.decision == GateDecision.DIGEST_MISMATCH
