"""Fault injection for security and integrity experiments.

IMPORTANT: All fault injection operates ONLY on copied fixtures
in isolated workspace directories. Never modifies original files.
"""

import json
import os
import random
import shutil
from pathlib import Path
from typing import Any, Optional

from traceai.hashing import hash_file
from traceai.logging_config import get_logger

logger = get_logger("faults.injector")


class FaultContext:
    """Context for a fault injection, tracking what was modified."""

    def __init__(self, scenario_id: str, work_dir: Path):
        self.scenario_id = scenario_id
        self.work_dir = work_dir
        self.original_hashes: dict[str, str] = {}
        self.modified_files: list[Path] = []
        self.metadata: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "work_dir": str(self.work_dir),
            "original_hashes": self.original_hashes,
            "modified_files": [str(f) for f in self.modified_files],
            "metadata": self.metadata,
        }


def prepare_workspace(
    source_dir: Path,
    work_dir: Path,
    scenario_id: str,
) -> FaultContext:
    """Copy fixtures to a workspace and record original hashes.

    All fault injection operates on this copy, never the originals.
    """
    ctx = FaultContext(scenario_id=scenario_id, work_dir=work_dir)

    # Clean and recreate work directory
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    # Copy source files
    if source_dir.is_dir():
        shutil.copytree(source_dir, work_dir, dirs_exist_ok=True)
    elif source_dir.is_file():
        shutil.copy2(source_dir, work_dir / source_dir.name)

    # Record original hashes
    for file_path in work_dir.rglob("*"):
        if file_path.is_file():
            rel = file_path.relative_to(work_dir)
            ctx.original_hashes[str(rel)] = hash_file(file_path)

    logger.info(
        f"Workspace prepared for {scenario_id}: "
        f"{len(ctx.original_hashes)} files in {work_dir}"
    )
    return ctx


def inject_model_weight_tampering(
    ctx: FaultContext,
    target_file: str = "model.safetensors",
    num_bytes: int = 16,
    seed: Optional[int] = None,
) -> FaultContext:
    """S1: Mutate bytes in a copied model weight file.

    Flips random bytes to simulate weight tampering.
    """
    if seed is not None:
        random.seed(seed)

    file_path = ctx.work_dir / target_file
    if not file_path.exists():
        # Try alternative filenames
        alternatives = list(ctx.work_dir.glob("*.bin")) + list(ctx.work_dir.glob("*.safetensors"))
        if alternatives:
            file_path = alternatives[0]
        else:
            logger.warning(f"No model file found to tamper in {ctx.work_dir}")
            ctx.metadata["fault_applied"] = False
            return ctx

    # Read, modify, write
    data = bytearray(file_path.read_bytes())
    positions = random.sample(range(min(len(data), 1024*1024)), min(num_bytes, len(data)))
    for pos in positions:
        data[pos] = (data[pos] + random.randint(1, 255)) % 256

    file_path.write_bytes(bytes(data))
    ctx.modified_files.append(file_path)
    ctx.metadata["fault_applied"] = True
    ctx.metadata["bytes_modified"] = len(positions)
    ctx.metadata["target_file"] = str(file_path.name)

    logger.info(f"S1: Tampered {len(positions)} bytes in {file_path.name}")
    return ctx


def inject_tokenizer_substitution(
    ctx: FaultContext,
    seed: Optional[int] = None,
) -> FaultContext:
    """S2: Substitute tokenizer files with modified versions."""
    if seed is not None:
        random.seed(seed)

    tokenizer_files = list(ctx.work_dir.glob("tokenizer*")) + list(ctx.work_dir.glob("vocab*"))
    if not tokenizer_files:
        logger.warning("No tokenizer files found to substitute")
        ctx.metadata["fault_applied"] = False
        return ctx

    for tf in tokenizer_files:
        if tf.is_file():
            data = tf.read_bytes()
            # Modify a small portion
            modified = bytearray(data)
            if len(modified) > 100:
                pos = random.randint(50, len(modified) - 50)
                modified[pos:pos+4] = b'\x00\x00\x00\x00'
            tf.write_bytes(bytes(modified))
            ctx.modified_files.append(tf)

    ctx.metadata["fault_applied"] = True
    ctx.metadata["files_modified"] = len(tokenizer_files)
    logger.info(f"S2: Substituted {len(tokenizer_files)} tokenizer files")
    return ctx


def inject_dataset_manifest_alteration(
    ctx: FaultContext,
    manifest_file: str = "manifest.json",
    seed: Optional[int] = None,
) -> FaultContext:
    """S3: Alter dataset manifest entries."""
    if seed is not None:
        random.seed(seed)

    manifest_path = ctx.work_dir / manifest_file
    if not manifest_path.exists():
        # Search for any JSON manifest
        manifests = list(ctx.work_dir.glob("*manifest*.json"))
        if manifests:
            manifest_path = manifests[0]
        else:
            logger.warning("No manifest file found")
            ctx.metadata["fault_applied"] = False
            return ctx

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # Alter a hash or entry
        if isinstance(manifest, dict):
            if "files" in manifest:
                files = manifest["files"]
                if files and isinstance(files, list):
                    idx = random.randint(0, len(files) - 1)
                    if isinstance(files[idx], dict) and "sha256" in files[idx]:
                        files[idx]["sha256"] = "a" * 64  # Fake hash
                        ctx.metadata["altered_entry"] = idx

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        ctx.modified_files.append(manifest_path)
        ctx.metadata["fault_applied"] = True
    except (json.JSONDecodeError, KeyError) as e:
        logger.error(f"Failed to alter manifest: {e}")
        ctx.metadata["fault_applied"] = False

    logger.info(f"S3: Altered dataset manifest {manifest_path.name}")
    return ctx


def inject_invalid_signature(
    ctx: FaultContext,
) -> FaultContext:
    """S9a: Create an invalid signature envelope."""
    ctx.metadata["fault_applied"] = True
    ctx.metadata["fault_type"] = "invalid_signature"
    ctx.metadata["invalid_sig"] = "deadbeef" * 16
    logger.info("S9a: Prepared invalid signature data")
    return ctx


def inject_unauthorized_signer(
    ctx: FaultContext,
) -> FaultContext:
    """S9b: Create a valid signature from an unauthorized signer."""
    ctx.metadata["fault_applied"] = True
    ctx.metadata["fault_type"] = "unauthorized_signer"
    ctx.metadata["signer_id"] = "unauthorized-attacker"
    logger.info("S9b: Prepared unauthorized signer scenario")
    return ctx


def inject_missing_model_digest_attestation(
    ctx: FaultContext,
) -> FaultContext:
    """S9c: Create attestation missing model digest."""
    ctx.metadata["fault_applied"] = True
    ctx.metadata["fault_type"] = "missing_model_digest"
    logger.info("S9c: Prepared attestation without model digest")
    return ctx


def inject_substituted_external_model(
    ctx: FaultContext,
    seed: Optional[int] = None,
) -> FaultContext:
    """S9d: Valid image with substituted externally mounted model."""
    if seed is not None:
        random.seed(seed)

    # Create a fake model file
    fake_model = ctx.work_dir / "substituted_model.bin"
    fake_model.write_bytes(os.urandom(1024))

    ctx.modified_files.append(fake_model)
    ctx.metadata["fault_applied"] = True
    ctx.metadata["fault_type"] = "substituted_model"
    ctx.metadata["fake_model_hash"] = hash_file(fake_model)
    logger.info("S9d: Created substituted external model")
    return ctx
