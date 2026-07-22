"""Application settings loaded from environment and config files."""

import os
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


class TraceAISettings(BaseSettings):
    """Global settings for TraceAI, loaded from environment variables and .env."""

    profile: Literal["local", "container", "industrial"] = "local"
    device: str = "auto"
    model_id: str = "openai-community/gpt2"
    model_revision: Optional[str] = None
    model_dir: Optional[str] = None
    results_root: Path = Path("results")
    workspace_root: Path = Path("workspace")
    max_host_gpu_memory_percent: int = 80
    max_host_ram_percent: int = 80
    max_test_duration_seconds: int = 300

    # External service placeholders
    harbor_url: Optional[str] = None
    harbor_project: Optional[str] = None
    dependency_track_url: Optional[str] = None
    dependency_track_api_key: Optional[str] = None
    cosign_key: Optional[str] = None
    kubeconfig: Optional[str] = None
    gitlab_url: Optional[str] = None
    gitlab_token: Optional[str] = None

    class Config:
        env_prefix = "TRACEAI_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def get_project_root() -> Path:
    """Return the project root directory."""
    # Walk up from this file to find pyproject.toml
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def load_profile_config(profile: str = "local") -> dict:
    """Load the YAML profile configuration."""
    root = get_project_root()
    config_path = root / "config" / "profiles" / f"{profile}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Profile config not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_experiment_config() -> dict:
    """Load the experiment configuration."""
    root = get_project_root()
    config_path = root / "config" / "experiment.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Experiment config not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_policy_config() -> dict:
    """Load the policy configuration."""
    root = get_project_root()
    config_path = root / "config" / "policy.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Policy config not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_settings() -> TraceAISettings:
    """Get application settings singleton."""
    return TraceAISettings()
