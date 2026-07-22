"""Deterministic hashing utilities for TraceAI."""

import hashlib
import json
from pathlib import Path
from typing import Any, Union


HASH_ALGORITHM = "sha256"
CHUNK_SIZE = 8192


def hash_file(path: Union[str, Path], algorithm: str = HASH_ALGORITHM) -> str:
    """Compute the hex digest of a file using the specified algorithm."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Cannot hash non-existent file: {path}")

    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


def hash_bytes(data: bytes, algorithm: str = HASH_ALGORITHM) -> str:
    """Compute the hex digest of raw bytes."""
    h = hashlib.new(algorithm)
    h.update(data)
    return h.hexdigest()


def hash_string(text: str, algorithm: str = HASH_ALGORITHM) -> str:
    """Compute the hex digest of a UTF-8 string."""
    return hash_bytes(text.encode("utf-8"), algorithm)


def hash_json(obj: Any, algorithm: str = HASH_ALGORITHM) -> str:
    """Compute a deterministic hash of a JSON-serializable object.

    Uses sorted keys and no whitespace for determinism.
    """
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return hash_string(canonical, algorithm)


def hash_directory(
    directory: Union[str, Path],
    algorithm: str = HASH_ALGORITHM,
    extensions: tuple[str, ...] = (),
) -> str:
    """Compute a deterministic hash over all files in a directory.

    Files are sorted by relative path for determinism.
    Optionally filter by file extensions.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    h = hashlib.new(algorithm)
    files = sorted(directory.rglob("*"))

    for file_path in files:
        if not file_path.is_file():
            continue
        if extensions and file_path.suffix not in extensions:
            continue

        # Include relative path in hash for structural integrity
        rel_path = file_path.relative_to(directory).as_posix()
        h.update(rel_path.encode("utf-8"))
        h.update(b"\x00")

        # Include file content
        with open(file_path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                h.update(chunk)
        h.update(b"\x01")  # Separator between files

    return h.hexdigest()


def verify_file_hash(
    path: Union[str, Path], expected_hash: str, algorithm: str = HASH_ALGORITHM
) -> bool:
    """Verify a file's hash matches the expected value."""
    actual = hash_file(path, algorithm)
    return actual == expected_hash


def generate_bom_ref(component_type: str, name: str, version: str = "") -> str:
    """Generate a stable, deterministic bom-ref identifier.

    Uses a hash of the component metadata to ensure stability across
    regeneration while maintaining uniqueness.
    """
    ref_input = f"{component_type}:{name}:{version}"
    digest = hash_string(ref_input)
    return f"ref-{component_type}-{digest[:16]}"
