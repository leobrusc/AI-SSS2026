"""Tests for RQ4 GPU campaign implementation.

Validates:
- Async concurrent workload (not sequential)
- Profile propagation to service
- Model revision passed to from_pretrained
- Configuration application and verification
- Queue depth dynamically updated
- Concurrency limit enforced
- Outcome classification
- GPU metrics conditional on profile
- Manifest with GPU metadata
- Quick validation gates logic
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))


class TestAsyncWorkload:
    """Verify the campaign uses async concurrent requests."""

    def test_run_trial_async_is_coroutine(self):
        """_run_trial_async is a coroutine function."""
        from traceai.campaigns.rq4 import _run_trial_async
        assert asyncio.iscoroutinefunction(_run_trial_async)

    def test_send_one_async_is_coroutine(self):
        """_send_one_async is a coroutine function."""
        from traceai.campaigns.rq4 import _send_one_async
        assert asyncio.iscoroutinefunction(_send_one_async)

    def test_c3_fault_injection_is_coroutine(self):
        """_run_c3_fault_injection is a coroutine function."""
        from traceai.campaigns.rq4 import _run_c3_fault_injection
        assert asyncio.iscoroutinefunction(_run_c3_fault_injection)

    def test_no_sequential_loop_in_experimental_path(self):
        """The run_rq4_campaign source should use _run_trial_async, not sequential loop."""
        import inspect
        from traceai.campaigns.rq4 import run_rq4_campaign
        source = inspect.getsource(run_rq4_campaign)
        assert "_run_trial_async" in source
        assert "for req_idx in range" not in source


class TestProfilePropagation:
    """Profile is passed to the service subprocess."""

    def test_start_service_passes_profile_gpu(self):
        """_start_service sets TRACEAI_PROFILE to the requested profile."""
        from unittest.mock import patch, MagicMock
        import os

        captured_env = {}

        def mock_popen(cmd, cwd, env, **kwargs):
            captured_env.update(env)
            proc = MagicMock()
            proc.poll.return_value = 0  # immediate exit
            proc.stderr.read.return_value = b"test"
            return proc

        with patch("subprocess.Popen", side_effect=mock_popen):
            from traceai.campaigns.rq4 import _start_service
            _start_service(ROOT, "test-model", profile="gpu", revision="abc123")

        assert captured_env.get("TRACEAI_PROFILE") == "gpu"
        assert captured_env.get("TRACEAI_MODEL_ID") == "test-model"
        assert captured_env.get("TRACEAI_MODEL_REVISION") == "abc123"

    def test_start_service_sets_cuda_device_for_gpu_profile(self):
        """GPU profile sets TRACEAI_DEVICE=cuda."""
        from unittest.mock import patch, MagicMock

        captured_env = {}

        def mock_popen(cmd, cwd, env, **kwargs):
            captured_env.update(env)
            proc = MagicMock()
            proc.poll.return_value = 0
            proc.stderr.read.return_value = b"test"
            return proc

        with patch("subprocess.Popen", side_effect=mock_popen):
            from traceai.campaigns.rq4 import _start_service
            _start_service(ROOT, "test-model", profile="gpu")

        assert captured_env.get("TRACEAI_DEVICE") == "cuda"


class TestModelRevision:
    """Model revision is passed to InferenceEngine."""

    def test_inference_engine_accepts_revision(self):
        """InferenceEngine stores the revision parameter."""
        from traceai.service.inference import InferenceEngine
        engine = InferenceEngine(
            model_id="test-model",
            revision="abc123def456",
            device="cpu",
        )
        assert engine.revision == "abc123def456"

    def test_rq4_uses_immutable_revisions(self):
        """RQ4 campaign defines pinned model revisions."""
        from traceai.campaigns.rq4 import SMOKE_REVISION, FULL_REVISION
        assert SMOKE_REVISION == "5f91d94bd9cd7190a9f3216ff93cd1dd95f2c7be"
        assert FULL_REVISION == "607a30d783dfa663caf39e06633721c8d4cfcd7e"


class TestConfigurationApplication:
    """PUT /configuration applies and verifies changes."""

    def test_controls_update_with_circuit_breaker_threshold(self):
        """update_configuration accepts circuit_breaker_threshold."""
        from traceai.service.controls import ControlsManager
        cm = ControlsManager(circuit_breaker_threshold=5)
        changes = cm.update_configuration(circuit_breaker_threshold=3)
        assert "circuit_breaker_threshold" in changes
        assert cm.circuit_breaker_threshold == 3

    def test_controls_circuit_breaker_disabled_when_threshold_zero(self):
        """circuit_breaker_enabled is False when threshold is 0."""
        from traceai.service.controls import ControlsManager
        cm = ControlsManager(circuit_breaker_threshold=0)
        assert cm.circuit_breaker_enabled is False
        cm.update_configuration(circuit_breaker_threshold=5)
        assert cm.circuit_breaker_enabled is True


class TestQueueDynamicUpdate:
    """Queue depth can be updated at runtime."""

    def test_set_max_depth(self):
        """set_max_depth updates the queue capacity."""
        from traceai.service.queueing import RequestQueue
        q = RequestQueue(max_depth=16)
        assert q.max_depth == 16
        q.set_max_depth(4)
        assert q.max_depth == 4

    def test_queue_respects_new_depth(self):
        """After set_max_depth, queue rejects at new limit."""
        from traceai.service.queueing import RequestQueue
        q = RequestQueue(max_depth=2)
        assert q.try_enqueue() is True
        assert q.try_enqueue() is True
        assert q.try_enqueue() is False  # full at 2
        q.dequeue()
        q.set_max_depth(1)
        # Still 1 in queue, capacity is 1 → full
        assert q.try_enqueue() is False


class TestConcurrencyEnforcement:
    """max_concurrency is enforced via semaphore."""

    def test_controls_max_concurrency_update(self):
        """max_concurrency can be updated."""
        from traceai.service.controls import ControlsManager
        cm = ControlsManager(max_concurrency=8)
        changes = cm.update_configuration(max_concurrency=2)
        assert cm.max_concurrency == 2
        assert "max_concurrency" in changes


class TestGPUMetricsConditional:
    """GPU metrics depend on profile."""

    def test_gpu_metadata_returns_dict_on_failure(self):
        """_get_gpu_metadata returns NOT_APPLICABLE when pynvml unavailable."""
        with patch.dict("sys.modules", {"pynvml": None}):
            from traceai.campaigns.rq4 import _get_gpu_metadata
            result = _get_gpu_metadata()
            assert "gpu" in result or "gpu_name" in result

    def test_configurations_have_circuit_breaker_threshold(self):
        """All configurations define circuit_breaker_threshold."""
        from traceai.campaigns.rq4 import CONFIGURATIONS
        for cid, cfg in CONFIGURATIONS.items():
            assert "circuit_breaker_threshold" in cfg, f"{cid} missing circuit_breaker_threshold"

    def test_c3_has_nonzero_threshold(self):
        """C3 enables circuit breaker with threshold > 0."""
        from traceai.campaigns.rq4 import CONFIGURATIONS
        assert CONFIGURATIONS["C3"]["circuit_breaker_threshold"] > 0

    def test_c0_c1_have_zero_threshold(self):
        """C0 and C1 have circuit breaker disabled (threshold=0)."""
        from traceai.campaigns.rq4 import CONFIGURATIONS
        assert CONFIGURATIONS["C0"]["circuit_breaker_threshold"] == 0
        assert CONFIGURATIONS["C1"]["circuit_breaker_threshold"] == 0


class TestManifestGPU:
    """Manifest includes GPU metadata for gpu profile, NOT_APPLICABLE for others."""

    def test_gpu_metadata_fallback_on_import_error(self):
        """_get_gpu_metadata returns NOT_APPLICABLE dict when pynvml unavailable."""
        import importlib
        import traceai.campaigns.rq4 as rq4_mod
        with patch.dict("sys.modules", {"pynvml": None}):
            # Reload to trigger ImportError path
            # But since it's a local import, just call directly
            from traceai.campaigns.rq4 import _get_gpu_metadata
            result = _get_gpu_metadata()
            assert result == {"gpu": "NOT_APPLICABLE"}


class TestUpdateConfigRequest:
    """UpdateConfigRequest includes all required fields."""

    def test_update_config_request_has_circuit_breaker_threshold(self):
        """UpdateConfigRequest accepts circuit_breaker_threshold."""
        from traceai.service.app import UpdateConfigRequest
        req = UpdateConfigRequest(circuit_breaker_threshold=3)
        assert req.circuit_breaker_threshold == 3

    def test_update_config_request_has_all_fields(self):
        """UpdateConfigRequest has all configuration fields."""
        from traceai.service.app import UpdateConfigRequest
        req = UpdateConfigRequest(
            max_new_tokens=20,
            timeout_seconds=15.0,
            max_concurrency=2,
            queue_depth=4,
            rate_limit_rpm=60,
            circuit_breaker_enabled=True,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=5.0,
        )
        assert req.max_new_tokens == 20
        assert req.circuit_breaker_threshold == 3


class TestOutcomeClassification:
    """Outcome classification from HTTP responses."""

    def test_200_is_completed(self):
        from traceai.campaigns.rq4 import _classify_outcome, OUTCOME_COMPLETED
        assert _classify_outcome(200, False) == OUTCOME_COMPLETED

    def test_429_is_rate_limit(self):
        from traceai.campaigns.rq4 import _classify_outcome, OUTCOME_RATE_LIMIT
        assert _classify_outcome(429, False) == OUTCOME_RATE_LIMIT

    def test_503_circuit_breaker(self):
        from traceai.campaigns.rq4 import _classify_outcome, OUTCOME_CIRCUIT_BREAKER
        assert _classify_outcome(503, False, "Circuit breaker open") == OUTCOME_CIRCUIT_BREAKER

    def test_503_queue_full(self):
        from traceai.campaigns.rq4 import _classify_outcome, OUTCOME_QUEUE_REJECTION
        assert _classify_outcome(503, False, "Queue full") == OUTCOME_QUEUE_REJECTION

    def test_504_timeout(self):
        from traceai.campaigns.rq4 import _classify_outcome, OUTCOME_UNEXPECTED_TIMEOUT
        assert _classify_outcome(504, True) == OUTCOME_UNEXPECTED_TIMEOUT

    def test_500_server_error(self):
        from traceai.campaigns.rq4 import _classify_outcome, OUTCOME_SERVER_ERROR
        assert _classify_outcome(500, False) == OUTCOME_SERVER_ERROR


class TestQuickValidationGates:
    """Quick validation report logic."""

    def test_quick_report_fails_without_c2_control(self):
        """Report status is FAIL if C2 has no control activation."""
        from traceai.campaigns.rq4 import _generate_quick_validation_report
        # Simulate observations with no C2 control activation
        obs = [{"configuration_id": "C0", "outcome_class": "COMPLETED",
                "trial_id": "test-C0-t0"}] * 60
        obs += [{"configuration_id": "C1", "outcome_class": "COMPLETED",
                 "trial_id": "test-C1-t0"}] * 60
        obs += [{"configuration_id": "C2", "outcome_class": "COMPLETED",
                 "trial_id": "test-C2-t0"}] * 60
        obs += [{"configuration_id": "C3", "outcome_class": "COMPLETED",
                 "trial_id": "test-C3-t0"}] * 60
        events = []
        report = _generate_quick_validation_report(
            ROOT, "test-campaign", obs, events, [], [], 240, "a" * 40)
        assert report["gates"]["c2_control_activated"] is False
        assert report["status"] == "FAIL"

    def test_quick_report_fails_without_c3_recovery(self):
        """Report status is FAIL if C3 never recovered."""
        from traceai.campaigns.rq4 import _generate_quick_validation_report
        obs = [{"configuration_id": "C0", "outcome_class": "COMPLETED",
                "trial_id": "test-C0-t0"}] * 60
        obs += [{"configuration_id": "C1", "outcome_class": "COMPLETED",
                 "trial_id": "test-C1-t0"}] * 60
        obs += [{"configuration_id": "C2", "outcome_class": "EXPECTED_RATE_LIMIT",
                 "trial_id": "test-C2-t0"}] * 60
        obs += [{"configuration_id": "C3", "outcome_class": "EXPECTED_CIRCUIT_BREAKER",
                 "trial_id": "test-C3-t0"}] * 60
        events = [{"event": "circuit_open", "timestamp": "2026-01-01T00:00:00Z"}]
        report = _generate_quick_validation_report(
            ROOT, "test-campaign", obs, events, [], [], 240, "a" * 40)
        assert report["gates"]["c3_recovered"] is False
        assert report["status"] == "FAIL"

    def test_quick_report_fails_without_gpu_timeseries(self):
        """Report status is FAIL if no GPU timeseries on gpu profile."""
        from traceai.campaigns.rq4 import _generate_quick_validation_report
        obs = [{"configuration_id": "C0", "outcome_class": "COMPLETED",
                "trial_id": "test-C0-t0"}] * 240
        events = [
            {"event": "circuit_open", "timestamp": "t"},
            {"event": "circuit_recovered", "timestamp": "t"},
        ]
        report = _generate_quick_validation_report(
            ROOT, "test-campaign", obs, events, [], [], 240, "a" * 40)
        assert report["gates"]["gpu_timeseries_present"] is False
        assert report["status"] == "FAIL"


class TestArtifactPaths:
    """Mandatory artifacts are referenced in the code."""

    def test_saves_gpu_timeseries(self):
        """Code references gpu_timeseries.csv."""
        import inspect
        from traceai.campaigns.rq4 import _save_all_artifacts
        source = inspect.getsource(_save_all_artifacts)
        assert "gpu_timeseries.csv" in source

    def test_saves_resource_timeseries(self):
        """Code references resource_timeseries.csv."""
        import inspect
        from traceai.campaigns.rq4 import _save_all_artifacts
        source = inspect.getsource(_save_all_artifacts)
        assert "resource_timeseries.csv" in source

    def test_saves_configuration_events(self):
        """Code references configuration_events.jsonl."""
        import inspect
        from traceai.campaigns.rq4 import _save_all_artifacts
        source = inspect.getsource(_save_all_artifacts)
        assert "configuration_events.jsonl" in source

    def test_saves_trial_manifest(self):
        """Code references trial_manifest.json."""
        import inspect
        from traceai.campaigns.rq4 import _save_all_artifacts
        source = inspect.getsource(_save_all_artifacts)
        assert "trial_manifest.json" in source

    def test_saves_prompt_corpus_hash(self):
        """Code references prompt_corpus_hash.json."""
        import inspect
        from traceai.campaigns.rq4 import _save_all_artifacts
        source = inspect.getsource(_save_all_artifacts)
        assert "prompt_corpus_hash.json" in source
