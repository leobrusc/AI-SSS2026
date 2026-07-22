"""Local ephemeral signing for test/local profile.

IMPORTANT: This is a local experimental substitute for demonstration
and testing purposes only. It is NOT Sigstore production evidence.
For container/industrial profiles, use Cosign with proper key management.
"""

import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)
from cryptography.x509 import (
    CertificateBuilder,
    Name,
    NameAttribute,
    BasicConstraints,
)
from cryptography.x509.oid import NameOID

from traceai.hashing import hash_json
from traceai.logging_config import get_logger

logger = get_logger("provenance.signer")


class LocalSigner:
    """Ephemeral ECDSA signer for local testing.

    Generates a new key pair for each session. Keys are stored
    under workspace/keys and are NOT suitable for production use.
    """

    def __init__(self, key_dir: Path, signer_id: str = "traceai-local-test"):
        self.key_dir = key_dir
        self.signer_id = signer_id
        self._private_key: Optional[ec.EllipticCurvePrivateKey] = None
        self._public_key = None
        self._key_path = key_dir / "ephemeral.key.pem"
        self._pub_path = key_dir / "ephemeral.pub.pem"

    def initialize(self, force_new: bool = False) -> None:
        """Initialize or load signing keys."""
        self.key_dir.mkdir(parents=True, exist_ok=True)

        if not force_new and self._key_path.exists():
            self._load_existing()
        else:
            self._generate_new()

    def _generate_new(self) -> None:
        """Generate a new ephemeral ECDSA key pair."""
        self._private_key = ec.generate_private_key(ec.SECP256R1())
        self._public_key = self._private_key.public_key()

        # Save private key (local test only)
        pem_private = self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        self._key_path.write_bytes(pem_private)

        # Save public key
        pem_public = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self._pub_path.write_bytes(pem_public)

        logger.info(f"Generated new ephemeral key pair in {self.key_dir}")

    def _load_existing(self) -> None:
        """Load existing key pair."""
        pem_data = self._key_path.read_bytes()
        self._private_key = serialization.load_pem_private_key(pem_data, password=None)
        self._public_key = self._private_key.public_key()
        logger.info(f"Loaded existing key pair from {self.key_dir}")

    def sign(self, payload: bytes) -> bytes:
        """Sign a payload with the ephemeral private key."""
        if self._private_key is None:
            raise RuntimeError("Signer not initialized. Call initialize() first.")

        signature = self._private_key.sign(payload, ec.ECDSA(hashes.SHA256()))
        return signature

    def sign_json(self, data: dict) -> dict:
        """Sign a JSON document, returning the document with signature envelope.

        Returns an envelope containing:
        - payload (base64 of canonical JSON)
        - signature (hex)
        - signer_id
        - timestamp
        - public_key_fingerprint
        """
        import base64

        canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = self.sign(canonical)

        # Public key fingerprint
        pub_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        from traceai.hashing import hash_bytes
        fingerprint = hash_bytes(pub_bytes)[:32]

        return {
            "payload": base64.b64encode(canonical).decode("ascii"),
            "payloadType": "application/json",
            "signatures": [
                {
                    "sig": signature.hex(),
                    "keyid": fingerprint,
                    "signer_id": self.signer_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ],
        }

    def get_public_key_pem(self) -> str:
        """Return the public key in PEM format."""
        if self._public_key is None:
            raise RuntimeError("Signer not initialized")
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

    def get_fingerprint(self) -> str:
        """Return the public key fingerprint."""
        if self._public_key is None:
            raise RuntimeError("Signer not initialized")
        pub_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        from traceai.hashing import hash_bytes
        return hash_bytes(pub_bytes)[:32]


def create_signer(key_dir: Optional[Path] = None, signer_id: str = "traceai-local-test") -> LocalSigner:
    """Factory for creating a local signer."""
    if key_dir is None:
        from traceai.settings import get_project_root
        key_dir = get_project_root() / "workspace" / "keys"

    signer = LocalSigner(key_dir=key_dir, signer_id=signer_id)
    signer.initialize()
    return signer
