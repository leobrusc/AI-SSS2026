"""Sanitization of results for publication.

Removes usernames, local paths, hostnames, internal IPs,
registry URLs, and tokens from publication outputs.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

from traceai.logging_config import get_logger

logger = get_logger("analysis.sanitization")

# Patterns to redact
SANITIZATION_PATTERNS = [
    # Windows paths with usernames
    (r"C:\\Users\\[^\\]+", r"C:\\Users\\<REDACTED>"),
    (r"/home/[^/]+", "/home/<REDACTED>"),
    # Hostnames and IPs
    (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "<REDACTED_IP>"),
    (r"\b[a-zA-Z0-9-]+\.internal\.[a-zA-Z]+\b", "<REDACTED_HOST>"),
    # Registry URLs
    (r"https?://[a-zA-Z0-9.-]+\.harbor\.[a-zA-Z]+", "<REDACTED_REGISTRY>"),
    (r"https?://registry\.[a-zA-Z0-9.-]+", "<REDACTED_REGISTRY>"),
    # Tokens and keys (hex strings > 32 chars)
    (r"\b[0-9a-fA-F]{40,}\b", "<REDACTED_TOKEN>"),
    # Email-like patterns
    (r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", "<REDACTED_EMAIL>"),
]


def sanitize_string(text: str) -> str:
    """Sanitize a string by replacing sensitive patterns."""
    result = text
    for pattern, replacement in SANITIZATION_PATTERNS:
        result = re.sub(pattern, replacement, result)
    return result


def sanitize_dict(data: dict[str, Any], depth: int = 0, max_depth: int = 20) -> dict[str, Any]:
    """Recursively sanitize a dictionary."""
    if depth > max_depth:
        return data

    sanitized = {}
    for key, value in data.items():
        # Skip sensitive keys entirely
        if key.lower() in ("password", "token", "secret", "api_key", "private_key"):
            sanitized[key] = "<REDACTED>"
            continue

        if isinstance(value, str):
            sanitized[key] = sanitize_string(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value, depth + 1, max_depth)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_dict(v, depth + 1, max_depth) if isinstance(v, dict)
                else sanitize_string(v) if isinstance(v, str)
                else v
                for v in value
            ]
        else:
            sanitized[key] = value

    return sanitized


def sanitize_file(input_path: Path, output_path: Path) -> None:
    """Sanitize a JSON file for publication."""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sanitized = sanitize_dict(data) if isinstance(data, dict) else data
    if isinstance(data, list):
        sanitized = [
            sanitize_dict(item) if isinstance(item, dict) else item
            for item in data
        ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sanitized, f, indent=2)

    logger.info(f"Sanitized: {input_path} -> {output_path}")


def create_public_bundle(
    results_dir: Path,
    public_dir: Path,
    campaign_id: str,
) -> Path:
    """Create a sanitized public bundle from campaign results."""
    bundle_dir = public_dir / campaign_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # Find and sanitize all JSON files in raw results
    raw_dir = results_dir / "raw"
    if raw_dir.exists():
        for json_file in raw_dir.rglob("*.json"):
            rel_path = json_file.relative_to(raw_dir)
            output_path = bundle_dir / rel_path
            sanitize_file(json_file, output_path)

    # Create bundle manifest
    manifest = {
        "campaign_id": campaign_id,
        "sanitized": True,
        "files": [
            str(f.relative_to(bundle_dir))
            for f in bundle_dir.rglob("*")
            if f.is_file()
        ],
    }
    manifest_path = bundle_dir / "MANIFEST.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Public bundle created: {bundle_dir} ({len(manifest['files'])} files)")
    return bundle_dir
