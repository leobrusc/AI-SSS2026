"""In-toto attestation generation and validation."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from traceai.hashing import hash_file, hash_json
from traceai.logging_config import get_logger

logger = get_logger("provenance.attestations")

INTOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
INTOTO_PREDICATE_TYPE = "https://traceai.dev/attestation/v1"


def create_attestation(
    subjects: list[dict[str, Any]],
    model_digest: str,
    tokenizer_digest: Optional[str] = None,
    sbom_digest: Optional[str] = None,
    bom_digest: Optional[str] = None,
    policy_version: str = "",
    source_revision: str = "",
    builder_id: str = "traceai-local",
    timestamp: Optional[str] = None,
) -> dict[str, Any]:
    """Create an in-toto attestation statement.

    Binds source revision, builder identity, timestamp, model digest,
    tokenizer digest, SBOM digest, AI/ML-BOM digest, and policy version.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    statement = {
        "_type": INTOTO_STATEMENT_TYPE,
        "subject": subjects,
        "predicateType": INTOTO_PREDICATE_TYPE,
        "predicate": {
            "builder": {"id": builder_id},
            "buildType": "https://traceai.dev/build/v1",
            "metadata": {
                "buildStartedOn": timestamp,
                "completeness": {
                    "parameters": True,
                    "environment": True,
                    "materials": True,
                },
            },
            "materials": [],
            "traceai": {
                "model_digest": model_digest,
                "tokenizer_digest": tokenizer_digest or "",
                "sbom_digest": sbom_digest or "",
                "bom_digest": bom_digest or "",
                "policy_version": policy_version,
                "source_revision": source_revision,
            },
        },
    }

    return statement


def create_subject(name: str, digest: str, algorithm: str = "sha256") -> dict[str, Any]:
    """Create an attestation subject entry."""
    return {
        "name": name,
        "digest": {algorithm: digest},
    }


def validate_attestation(attestation: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate attestation structure and required fields.

    Returns (is_valid, list_of_errors).
    """
    errors = []

    if attestation.get("_type") != INTOTO_STATEMENT_TYPE:
        errors.append(f"Invalid statement type: {attestation.get('_type')}")

    subjects = attestation.get("subject", [])
    if not subjects:
        errors.append("No subjects in attestation")

    for i, subj in enumerate(subjects):
        if "name" not in subj:
            errors.append(f"Subject {i} missing 'name'")
        if "digest" not in subj:
            errors.append(f"Subject {i} missing 'digest'")

    predicate = attestation.get("predicate", {})
    if not predicate:
        errors.append("Missing predicate")
    else:
        traceai_data = predicate.get("traceai", {})
        if not traceai_data.get("model_digest"):
            errors.append("Attestation missing model_digest in traceai predicate")

    return (len(errors) == 0, errors)


def verify_attestation_subjects(
    attestation: dict[str, Any],
    observed_digests: dict[str, str],
) -> tuple[bool, list[str]]:
    """Verify attestation subjects match observed digests.

    Args:
        attestation: The attestation statement
        observed_digests: Map of subject name -> observed digest

    Returns (all_match, list_of_mismatches).
    """
    mismatches = []
    subjects = attestation.get("subject", [])

    for subj in subjects:
        name = subj.get("name", "")
        attested_digest = subj.get("digest", {}).get("sha256", "")

        if name in observed_digests:
            if attested_digest != observed_digests[name]:
                mismatches.append(
                    f"Subject '{name}': attested={attested_digest[:16]}... "
                    f"observed={observed_digests[name][:16]}..."
                )

    return (len(mismatches) == 0, mismatches)


def save_attestation(attestation: dict[str, Any], path: Path) -> None:
    """Save attestation to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(attestation, f, indent=2)
    logger.info(f"Attestation saved: {path}")


def load_attestation(path: Path) -> Optional[dict[str, Any]]:
    """Load attestation from file."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load attestation from {path}: {e}")
        return None
