"""Fixture restoration and verification after fault injection."""

import shutil
from pathlib import Path

from traceai.faults.injector import FaultContext
from traceai.hashing import hash_file
from traceai.logging_config import get_logger

logger = get_logger("faults.restore")


class RestorationResult:
    """Result of restoring fixtures after fault injection."""

    def __init__(self):
        self.success = True
        self.files_restored = 0
        self.files_verified = 0
        self.hash_mismatches: list[str] = []

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "files_restored": self.files_restored,
            "files_verified": self.files_verified,
            "hash_mismatches": self.hash_mismatches,
        }


def restore_from_context(
    ctx: FaultContext,
    source_dir: Path,
) -> RestorationResult:
    """Restore workspace from original source and verify hashes.

    Args:
        ctx: The fault context with original hashes
        source_dir: The original unmodified source directory

    Returns:
        RestorationResult with verification details
    """
    result = RestorationResult()

    # Remove modified workspace
    if ctx.work_dir.exists():
        shutil.rmtree(ctx.work_dir)

    # Re-copy from source
    ctx.work_dir.mkdir(parents=True, exist_ok=True)
    if source_dir.is_dir():
        shutil.copytree(source_dir, ctx.work_dir, dirs_exist_ok=True)
    elif source_dir.is_file():
        shutil.copy2(source_dir, ctx.work_dir / source_dir.name)

    result.files_restored = sum(1 for _ in ctx.work_dir.rglob("*") if _.is_file())

    # Verify hashes match originals
    for rel_path, original_hash in ctx.original_hashes.items():
        file_path = ctx.work_dir / rel_path
        if not file_path.exists():
            result.hash_mismatches.append(f"Missing: {rel_path}")
            result.success = False
            continue

        current_hash = hash_file(file_path)
        if current_hash == original_hash:
            result.files_verified += 1
        else:
            result.hash_mismatches.append(
                f"Hash mismatch: {rel_path} "
                f"(expected {original_hash[:16]}..., got {current_hash[:16]}...)"
            )
            result.success = False

    if result.success:
        logger.info(
            f"Restoration verified: {result.files_verified}/{len(ctx.original_hashes)} files OK"
        )
    else:
        logger.error(
            f"Restoration FAILED: {len(result.hash_mismatches)} mismatches"
        )

    return result


def cleanup_workspace(work_dir: Path) -> None:
    """Remove a temporary workspace directory."""
    if work_dir.exists():
        shutil.rmtree(work_dir)
        logger.debug(f"Cleaned up workspace: {work_dir}")
