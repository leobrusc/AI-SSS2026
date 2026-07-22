"""Unit tests for traceai.hashing module."""

import os

import pytest

from traceai.hashing import (
    generate_bom_ref,
    hash_bytes,
    hash_file,
    hash_json,
    hash_string,
    verify_file_hash,
)

pytestmark = pytest.mark.unit


class TestHashFile:
    """Tests for hash_file function."""

    def test_hash_file_deterministic(self, tmp_path):
        """Hashing the same file twice must produce the same digest."""
        f = tmp_path / "data.bin"
        f.write_bytes(b"deterministic content")

        h1 = hash_file(f)
        h2 = hash_file(f)

        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex length


class TestHashBytes:
    """Tests for hash_bytes function."""

    def test_hash_bytes(self):
        """Hashing raw bytes returns a stable hex digest."""
        data = b"hello world"
        digest = hash_bytes(data)

        assert isinstance(digest, str)
        assert len(digest) == 64
        # Known SHA-256 of "hello world"
        assert digest == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


class TestHashString:
    """Tests for hash_string function."""

    def test_hash_string(self):
        """Hashing a string produces a deterministic hex digest."""
        text = "traceai"
        d1 = hash_string(text)
        d2 = hash_string(text)

        assert d1 == d2
        assert len(d1) == 64


class TestHashJson:
    """Tests for hash_json function."""

    def test_hash_json_deterministic(self):
        """Same dict with different key order must produce the same hash."""
        dict_a = {"z": 1, "a": 2, "m": [3, 4]}
        dict_b = {"a": 2, "m": [3, 4], "z": 1}

        assert hash_json(dict_a) == hash_json(dict_b)


class TestGenerateBomRef:
    """Tests for generate_bom_ref function."""

    def test_generate_bom_ref_stable(self):
        """The same inputs must always produce the same bom-ref."""
        ref1 = generate_bom_ref("library", "numpy", "1.26.0")
        ref2 = generate_bom_ref("library", "numpy", "1.26.0")

        assert ref1 == ref2
        assert ref1.startswith("ref-library-")


class TestVerifyFileHash:
    """Tests for verify_file_hash function."""

    def test_verify_file_hash_positive(self, tmp_path):
        """Verification passes when hash matches."""
        f = tmp_path / "artifact.bin"
        content = b"known content for hash check"
        f.write_bytes(content)

        expected = hash_file(f)
        assert verify_file_hash(f, expected) is True

    def test_verify_file_hash_negative(self, tmp_path):
        """Verification fails when hash does not match."""
        f = tmp_path / "artifact.bin"
        f.write_bytes(b"original content")

        wrong_hash = "0" * 64
        assert verify_file_hash(f, wrong_hash) is False
