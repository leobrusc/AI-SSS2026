"""
Camera-Ready RQ2 Extension Campaign
CAMERA_READY_EXTENSION

Scenarios:
  CR-SIG    : authorized signer with tampered signature bytes
  CR-META   : metadata substitution (revision/identity fields)
  CR-REPLAY-EXPIRED : valid evidence replayed after freshness window
  CR-REPLAY-FRESH   : valid evidence replayed within freshness window
  CR-ROLLBACK       : older valid revision replayed as current
  CR-REVOKED        : allowlist removal simulation

All outputs go to results/camera_ready/rq2_extension/
"""

import base64
import csv
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.exceptions import InvalidSignature

from traceai.provenance.signer import LocalSigner
from traceai.provenance.verifier import LocalVerifier
from traceai.provenance.attestations import create_attestation, create_subject
from traceai.hashing import hash_bytes
from traceai.models import GateDecision

CAMPAIGN_ID = f"camera-ready-rq2-ext-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{''.join(list(uuid.uuid4().hex[:8]))}"
OUT_DIR = ROOT / "results" / "camera_ready" / "rq2_extension"
GEN_DIR = ROOT / "generated" / "camera_ready" / "rq2_extension"
OUT_DIR.mkdir(parents=True, exist_ok=True)
GEN_DIR.mkdir(parents=True, exist_ok=True)

KEY_DIR = ROOT / "workspace" / "camera_ready_keys"
KEY_DIR.mkdir(parents=True, exist_ok=True)

ROWS = []

# ──────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────

def make_signer(suffix: str) -> LocalSigner:
    kd = KEY_DIR / suffix
    kd.mkdir(parents=True, exist_ok=True)
    s = LocalSigner(key_dir=kd, signer_id=f"traceai-cr-{suffix}")
    s.initialize(force_new=True)
    return s


def make_artifact(seed: int, size: int = 512) -> bytes:
    import random
    rng = random.Random(seed)
    return bytes(rng.getrandbits(8) for _ in range(size))


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record(scenario_id, trial, seed, artifact_digest, artifact_revision,
           signer_id, key_fingerprint, sig_modified, meta_modified,
           evidence_timestamp, evidence_age_seconds, expected, observed,
           reason_code, verification_path, pass_fail, notes=""):
    ROWS.append({
        "campaign_id": CAMPAIGN_ID,
        "campaign_type": "CAMERA_READY_EXTENSION",
        "scenario_id": scenario_id,
        "trial": trial,
        "seed": seed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "artifact_digest": artifact_digest[:16] + "...",
        "artifact_revision": artifact_revision,
        "signer_id": signer_id,
        "key_fingerprint": key_fingerprint[:16] + "..." if key_fingerprint else "",
        "signature_modified": sig_modified,
        "metadata_modified": meta_modified,
        "evidence_timestamp": evidence_timestamp,
        "evidence_age_seconds": evidence_age_seconds,
        "expected_decision": expected,
        "observed_decision": observed,
        "reason_code": reason_code,
        "verification_path": verification_path,
        "pass_fail": pass_fail,
        "notes": notes,
    })


# ──────────────────────────────────────────────
# CR-SIG: authorized signer, tampered sig bytes
# ──────────────────────────────────────────────
print("=== CR-SIG: AUTHORIZED_SIGNER_INVALID_SIGNATURE ===")
cr_sig_signer = make_signer("cr_sig")
cr_sig_fp = cr_sig_signer.get_fingerprint()
verifier_cr_sig = LocalVerifier(
    allowed_fingerprints=[cr_sig_fp],
    max_evidence_age_hours=24
)

CR_SIG_RESULTS = []
for trial in range(30):
    seed = 1000 + trial
    artifact = make_artifact(seed)
    digest = sha256_hex(artifact)

    # 1. Produce valid attestation and sign it
    attestation = create_attestation(
        subjects=[create_subject("model", digest)],
        model_digest=digest,
    )
    envelope = cr_sig_signer.sign_json(attestation)

    # 2. Confirm envelope has the authorized keyid
    original_keyid = envelope["signatures"][0]["keyid"]
    assert original_keyid == cr_sig_fp, f"keyid mismatch: {original_keyid} != {cr_sig_fp}"

    # 3. Tamper ONLY the sig bytes — keep keyid unchanged
    original_sig_hex = envelope["signatures"][0]["sig"]
    original_sig_bytes = bytes.fromhex(original_sig_hex)
    # flip one byte deterministically
    tampered = bytearray(original_sig_bytes)
    tampered[seed % len(tampered)] ^= 0xFF
    envelope["signatures"][0]["sig"] = bytes(tampered).hex()

    assert envelope["signatures"][0]["keyid"] == cr_sig_fp, "keyid must remain authorized"
    assert envelope["signatures"][0]["sig"] != original_sig_hex, "sig must differ"

    # 4. Verify — must pass authorization, reach ECDSA
    result = verifier_cr_sig.verify_signature(
        envelope=envelope,
        public_key_pem=cr_sig_signer.get_public_key_pem(),
    )

    # Track whether ECDSA path was reached (not UNAUTHORIZED_SIGNER)
    ecdsa_reached = result.decision != GateDecision.UNAUTHORIZED_SIGNER
    expected = GateDecision.INVALID_SIGNATURE.value
    observed = result.decision.value
    passed = (observed == expected) and ecdsa_reached

    CR_SIG_RESULTS.append(passed)
    path = "ECDSA_VERIFY" if ecdsa_reached else "SIGNER_AUTH_ONLY"

    record("CR-SIG", trial, seed, digest, "N/A",
           cr_sig_signer.signer_id, cr_sig_fp,
           sig_modified=True, meta_modified=False,
           evidence_timestamp=envelope["signatures"][0]["timestamp"],
           evidence_age_seconds=0,
           expected=expected, observed=observed,
           reason_code=result.reason,
           verification_path=path,
           pass_fail="PASS" if passed else "FAIL",
           notes=f"ecdsa_reached={ecdsa_reached}")

cr_sig_pass = sum(CR_SIG_RESULTS)
print(f"  CR-SIG: {cr_sig_pass}/30 PASS  (ECDSA reached in all trials: {all(r['verification_path'] == 'ECDSA_VERIFY' for r in ROWS if r['scenario_id']=='CR-SIG')})")
