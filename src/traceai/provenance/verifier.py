"""Signature and attestation verification for deployment gates."""

import base64
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.exceptions import InvalidSignature

from traceai.logging_config import get_logger
from traceai.models import GateDecision

logger = get_logger("provenance.verifier")


class VerificationResult:
    """Result of a verification operation."""

    def __init__(self):
        self.decision: GateDecision = GateDecision.APPROVED
        self.reason: str = ""
        self.details: dict[str, Any] = {}
        self.latency_ms: float = 0.0

    @property
    def approved(self) -> bool:
        return self.decision == GateDecision.APPROVED

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason": self.reason,
            "approved": self.approved,
            "latency_ms": self.latency_ms,
            "details": self.details,
        }


class LocalVerifier:
    """Verifies signatures and attestations using local ephemeral keys."""

    def __init__(self, allowed_fingerprints: list[str], max_evidence_age_hours: int = 24):
        self.allowed_fingerprints = allowed_fingerprints
        self.max_evidence_age_hours = max_evidence_age_hours

    def verify_signature(self, envelope: dict[str, Any], public_key_pem: str) -> VerificationResult:
        """Verify a signed envelope.

        Checks:
        1. Valid cryptographic signature
        2. Signer is in allowed list
        3. Evidence is not stale
        """
        result = VerificationResult()
        start = time.time()

        try:
            # Load public key
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode("ascii")
            )

            # Get payload and signature
            payload_b64 = envelope.get("payload", "")
            payload = base64.b64decode(payload_b64)

            signatures = envelope.get("signatures", [])
            if not signatures:
                result.decision = GateDecision.INVALID_SIGNATURE
                result.reason = "No signatures in envelope"
                result.latency_ms = (time.time() - start) * 1000
                return result

            sig_entry = signatures[0]
            sig_bytes = bytes.fromhex(sig_entry.get("sig", ""))
            key_id = sig_entry.get("keyid", "")
            signer_id = sig_entry.get("signer_id", "")
            sig_timestamp = sig_entry.get("timestamp", "")

            # Check signer authorization
            if self.allowed_fingerprints and key_id not in self.allowed_fingerprints:
                result.decision = GateDecision.UNAUTHORIZED_SIGNER
                result.reason = f"Signer '{signer_id}' (key {key_id[:8]}...) not in allowed list"
                result.latency_ms = (time.time() - start) * 1000
                return result

            # Check evidence age
            if sig_timestamp and self.max_evidence_age_hours > 0:
                try:
                    sig_time = datetime.fromisoformat(sig_timestamp)
                    age = datetime.now(timezone.utc) - sig_time
                    if age > timedelta(hours=self.max_evidence_age_hours):
                        result.decision = GateDecision.STALE_EVIDENCE
                        result.reason = f"Evidence age {age} exceeds max {self.max_evidence_age_hours}h"
                        result.latency_ms = (time.time() - start) * 1000
                        return result
                except (ValueError, TypeError):
                    pass

            # Verify cryptographic signature
            public_key.verify(sig_bytes, payload, ec.ECDSA(hashes.SHA256()))

            result.decision = GateDecision.APPROVED
            result.reason = "Signature valid"
            result.details = {"signer_id": signer_id, "key_id": key_id[:16]}

        except InvalidSignature:
            result.decision = GateDecision.INVALID_SIGNATURE
            result.reason = "Cryptographic signature verification failed"
        except Exception as e:
            result.decision = GateDecision.INVALID_SIGNATURE
            result.reason = f"Verification error: {str(e)}"

        result.latency_ms = (time.time() - start) * 1000
        return result

    def verify_attestation_completeness(
        self, attestation: dict[str, Any]
    ) -> VerificationResult:
        """Verify attestation has all required fields."""
        result = VerificationResult()
        start = time.time()

        predicate = attestation.get("predicate", {})
        traceai_data = predicate.get("traceai", {})

        if not traceai_data.get("model_digest"):
            result.decision = GateDecision.MISSING_ATTESTATION
            result.reason = "Attestation missing model_digest"
        elif not attestation.get("subject"):
            result.decision = GateDecision.MISSING_ATTESTATION
            result.reason = "Attestation has no subjects"
        else:
            result.decision = GateDecision.APPROVED
            result.reason = "Attestation complete"

        result.latency_ms = (time.time() - start) * 1000
        return result

    def verify_digest_match(
        self,
        attested_digest: str,
        observed_digest: str,
        artifact_name: str = "artifact",
    ) -> VerificationResult:
        """Verify an attested digest matches the observed digest."""
        result = VerificationResult()
        start = time.time()

        if not attested_digest:
            result.decision = GateDecision.MISSING_ARTIFACT
            result.reason = f"No attested digest for {artifact_name}"
        elif attested_digest != observed_digest:
            result.decision = GateDecision.DIGEST_MISMATCH
            result.reason = (
                f"{artifact_name} digest mismatch: "
                f"attested={attested_digest[:16]}... "
                f"observed={observed_digest[:16]}..."
            )
            result.details = {
                "attested": attested_digest,
                "observed": observed_digest,
            }
        else:
            result.decision = GateDecision.APPROVED
            result.reason = f"{artifact_name} digest verified"

        result.latency_ms = (time.time() - start) * 1000
        return result


def create_verifier(
    allowed_fingerprints: Optional[list[str]] = None,
    max_evidence_age_hours: int = 24,
) -> LocalVerifier:
    """Factory for creating a local verifier."""
    return LocalVerifier(
        allowed_fingerprints=allowed_fingerprints or [],
        max_evidence_age_hours=max_evidence_age_hours,
    )
