"""Integration smoke tests for the inference service layer."""

import pytest

pytestmark = pytest.mark.integration


class TestInferenceEngineImport:
    """Tests verifying the InferenceEngine class is importable and well-formed."""

    def test_inference_engine_class_exists(self):
        """InferenceEngine class can be imported from traceai.service.inference."""
        from traceai.service.inference import InferenceEngine

        assert InferenceEngine is not None
        # Verify it has the expected interface
        engine = InferenceEngine(model_id="test-model", device="cpu")
        assert hasattr(engine, "load")
        assert hasattr(engine, "generate")
        assert hasattr(engine, "unload")
        assert engine.is_loaded is False


class TestGenerateRequestModel:
    """Tests for the GenerateRequest Pydantic model."""

    def test_generate_request_validates(self):
        """GenerateRequest model accepts valid input."""
        from traceai.service.app import GenerateRequest

        req = GenerateRequest(
            prompt="Hello world",
            max_new_tokens=50,
            temperature=0.8,
            seed=42,
        )

        assert req.prompt == "Hello world"
        assert req.max_new_tokens == 50
        assert req.temperature == 0.8
        assert req.seed == 42

    def test_generate_request_defaults(self):
        """GenerateRequest model uses defaults for optional fields."""
        from traceai.service.app import GenerateRequest

        req = GenerateRequest(prompt="test prompt")

        assert req.prompt == "test prompt"
        assert req.max_new_tokens is None
        assert req.temperature == 1.0
        assert req.seed is None


class TestHealthEndpointSchema:
    """Tests for the health endpoint response schema."""

    def test_health_response_schema(self):
        """HealthResponse model has expected fields."""
        from traceai.service.app import HealthResponse

        health = HealthResponse(
            status="ok",
            timestamp="2026-07-22T00:00:00Z",
            uptime_seconds=120.5,
        )

        assert health.status == "ok"
        assert health.timestamp == "2026-07-22T00:00:00Z"
        assert health.uptime_seconds == 120.5
