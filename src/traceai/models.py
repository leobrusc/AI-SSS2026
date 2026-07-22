"""Shared data models for TraceAI experiments."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class GateDecision(str, Enum):
    """Deployment gate decision codes."""
    APPROVED = "APPROVED"
    MISSING_ARTIFACT = "MISSING_ARTIFACT"
    DIGEST_MISMATCH = "DIGEST_MISMATCH"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    UNAUTHORIZED_SIGNER = "UNAUTHORIZED_SIGNER"
    MISSING_ATTESTATION = "MISSING_ATTESTATION"
    ATTESTATION_DIGEST_MISMATCH = "ATTESTATION_DIGEST_MISMATCH"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    VEX_MALFORMED = "VEX_MALFORMED"
    VEX_EXPIRED = "VEX_EXPIRED"
    VEX_WRONG_COMPONENT = "VEX_WRONG_COMPONENT"
    VEX_UNSIGNED = "VEX_UNSIGNED"
    CRITICAL_VULNERABILITY = "CRITICAL_VULNERABILITY"
    CONFIGURATION_DRIFT = "CONFIGURATION_DRIFT"
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"


class TrialResult(BaseModel):
    """Result of a single experiment trial."""
    trial_id: str
    scenario_id: str
    scenario_name: str
    profile: str
    timestamp: datetime
    seed: int
    decision: GateDecision
    reason_code: str
    detection_latency_ms: float
    false_positive: bool = False
    false_negative: bool = False
    input_hashes: dict[str, str] = Field(default_factory=dict)
    restoration_verified: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class RequestObservation(BaseModel):
    """Observation from a single inference request."""
    request_id: str
    trial_id: str
    configuration_id: str
    timestamp: datetime
    latency_ms: float
    status_code: int
    tokens_generated: int
    timed_out: bool = False
    rejected: bool = False
    rejection_reason: Optional[str] = None
    queue_depth_at_request: int = 0
    active_workers: int = 0
    cpu_percent: Optional[float] = None
    ram_mb: Optional[float] = None
    gpu_utilization_percent: Optional[float] = None
    gpu_memory_mb: Optional[float] = None
    gpu_temperature_c: Optional[float] = None
    gpu_power_w: Optional[float] = None


class CampaignManifest(BaseModel):
    """Manifest for a complete campaign run."""
    campaign_id: str
    campaign_type: str  # security | availability | overhead
    profile: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    trial_count: int
    requests_per_trial: int = 0
    configurations: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)
    model_id: str = ""
    model_revision: str = ""
    device: str = ""
    seed_base: int = 42
    raw_directory: str = ""
    file_hashes: dict[str, str] = Field(default_factory=dict)
    status: str = "running"  # running | completed | failed | aborted


class VulnerabilityFinding(BaseModel):
    """Normalized vulnerability finding from scanners."""
    vulnerability_id: str
    package_url: Optional[str] = None
    package_name: str
    installed_version: str
    severity: str  # CRITICAL | HIGH | MEDIUM | LOW | UNKNOWN
    fix_version: Optional[str] = None
    scanner: str  # trivy | grype
    vex_status: Optional[str] = None  # not_affected | affected | fixed | under_investigation


class OverheadMeasurement(BaseModel):
    """Timing measurement for pipeline overhead."""
    operation: str
    duration_ms: float
    artifact_size_bytes: Optional[int] = None
    is_one_time: bool = False
    profile: str = "local"
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
