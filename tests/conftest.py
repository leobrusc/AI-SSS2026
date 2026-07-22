"""Shared pytest fixtures for TraceAI test suite."""

import json
import os
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    """Return the absolute path to the project root."""
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """Create and return a temporary workspace directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


@pytest.fixture
def sample_model_fixture(tmp_path: Path) -> Path:
    """Create a temporary file with random bytes simulating a model artifact."""
    model_file = tmp_path / "model.safetensors"
    model_file.write_bytes(os.urandom(4096))
    return model_file


@pytest.fixture
def sample_vex_valid(project_root: Path) -> dict:
    """Load the valid VEX fixture (not_affected.valid.json)."""
    vex_path = project_root / "fixtures" / "vex" / "not_affected.valid.json"
    with open(vex_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_vex_malformed(project_root: Path) -> dict:
    """Load the malformed VEX fixture (malformed.json)."""
    vex_path = project_root / "fixtures" / "vex" / "malformed.json"
    with open(vex_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def policy_engine():
    """Create a PolicyEngine instance with default config."""
    from traceai.policy.engine import PolicyEngine

    return PolicyEngine(policy_config={
        "mode": "fail-closed",
        "vulnerability": {
            "vex_policy": {
                "reject_expired": True,
                "reject_wrong_component": True,
                "require_signature": False,
            }
        },
        "runtime": {
            "verify_configuration_digest": True,
        },
    })


@pytest.fixture
def local_signer(tmp_path: Path):
    """Create a LocalSigner with ephemeral keys in a temp directory."""
    from traceai.provenance.signer import create_signer

    key_dir = tmp_path / "keys"
    key_dir.mkdir(parents=True, exist_ok=True)
    return create_signer(key_dir=key_dir, signer_id="test-signer")
