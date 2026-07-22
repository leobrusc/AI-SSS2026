"""Unit tests for traceai.faults (injector and restore) module."""

import os

import pytest

from traceai.faults.injector import (
    inject_model_weight_tampering,
    prepare_workspace,
)
from traceai.faults.restore import restore_from_context
from traceai.hashing import hash_file

pytestmark = pytest.mark.unit


class TestPrepareWorkspace:
    """Tests for prepare_workspace function."""

    def test_prepare_workspace_copies_files(self, tmp_path):
        """prepare_workspace copies source files and records hashes."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "model.bin").write_bytes(os.urandom(512))
        (source_dir / "config.json").write_text('{"key": "value"}', encoding="utf-8")

        work_dir = tmp_path / "work"

        ctx = prepare_workspace(source_dir, work_dir, "test-scenario")

        # Files should be copied
        assert (work_dir / "model.bin").exists()
        assert (work_dir / "config.json").exists()

        # Hashes should be recorded
        assert len(ctx.original_hashes) == 2
        assert "model.bin" in ctx.original_hashes
        assert "config.json" in ctx.original_hashes


class TestInjectModelTampering:
    """Tests for inject_model_weight_tampering function."""

    def test_inject_model_tampering_changes_hash(self, tmp_path):
        """Tampering a model file must change its hash."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        model_file = source_dir / "model.safetensors"
        model_file.write_bytes(os.urandom(2048))

        work_dir = tmp_path / "work"
        ctx = prepare_workspace(source_dir, work_dir, "tamper-test")

        original_hash = ctx.original_hashes["model.safetensors"]

        # Inject tampering
        ctx = inject_model_weight_tampering(ctx, target_file="model.safetensors", seed=42)

        # Hash must have changed
        new_hash = hash_file(work_dir / "model.safetensors")
        assert new_hash != original_hash
        assert ctx.metadata["fault_applied"] is True


class TestRestore:
    """Tests for restore_from_context function."""

    def test_restore_verifies_hashes(self, tmp_path):
        """Restoration from clean source verifies all hashes match."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "model.bin").write_bytes(os.urandom(1024))
        (source_dir / "tokenizer.json").write_text('{}', encoding="utf-8")

        work_dir = tmp_path / "work"
        ctx = prepare_workspace(source_dir, work_dir, "restore-test")

        # Tamper and then restore
        (work_dir / "model.bin").write_bytes(b"tampered!")

        result = restore_from_context(ctx, source_dir)

        assert result.success is True
        assert result.files_verified == 2
        assert result.hash_mismatches == []

    def test_restore_detects_mismatch(self, tmp_path):
        """Restoration detects hash mismatch if source was modified."""
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        (source_dir / "model.bin").write_bytes(b"original")

        work_dir = tmp_path / "work"
        ctx = prepare_workspace(source_dir, work_dir, "mismatch-test")

        # Modify the SOURCE so that restored copy won't match original hash
        (source_dir / "model.bin").write_bytes(b"source-was-modified")

        result = restore_from_context(ctx, source_dir)

        assert result.success is False
        assert len(result.hash_mismatches) > 0
