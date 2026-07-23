"""FastAPI inference service with runtime controls."""

import asyncio
import json
import signal
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from traceai.hashing import hash_json
from traceai.logging_config import get_logger, setup_logging
from traceai.service.controls import ControlsManager
from traceai.service.inference import InferenceEngine
from traceai.service.queueing import RequestQueue
from traceai.service.telemetry import TelemetryCollector
from traceai.settings import get_settings, load_profile_config

logger = get_logger("service.app")


class GenerateRequest(BaseModel):
    """Request body for text generation."""
    prompt: str
    max_new_tokens: Optional[int] = None
    temperature: float = 1.0
    seed: Optional[int] = None
    request_id: Optional[str] = None


class GenerateResponse(BaseModel):
    """Response body for text generation."""
    request_id: str
    text: str
    tokens_generated: int
    latency_ms: float
    model_id: str
    configuration_digest: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: str
    uptime_seconds: float


class ConfigurationResponse(BaseModel):
    """Service configuration response."""
    max_new_tokens: int
    timeout_seconds: float
    max_concurrency: int
    queue_depth: int
    rate_limit_rpm: int
    circuit_breaker_enabled: bool
    configuration_digest: str
    model_id: str
    device: str


# Global state
_app_state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    setup_logging()
    settings = get_settings()
    profile_config = load_profile_config(settings.profile)

    logger.info(f"Starting TraceAI service with profile: {settings.profile}")

    # Initialize components
    inference_cfg = profile_config.get("inference", {})
    controls = ControlsManager(
        max_new_tokens=inference_cfg.get("max_new_tokens", 100),
        timeout_seconds=inference_cfg.get("timeout_seconds", 30),
        max_concurrency=inference_cfg.get("max_concurrency", 4),
        queue_depth=inference_cfg.get("queue_depth", 16),
        rate_limit_rpm=inference_cfg.get("rate_limit_rpm", 120),
        circuit_breaker_threshold=inference_cfg.get("circuit_breaker_threshold", 5),
        circuit_breaker_timeout=inference_cfg.get("circuit_breaker_timeout", 30),
    )

    engine = InferenceEngine(
        model_id=settings.model_id,
        model_dir=settings.model_dir,
        device=settings.device,
        max_new_tokens=controls.max_new_tokens,
    )
    await engine.load()

    queue = RequestQueue(max_depth=controls.queue_depth)
    telemetry = TelemetryCollector()

    _app_state["controls"] = controls
    _app_state["engine"] = engine
    _app_state["queue"] = queue
    _app_state["telemetry"] = telemetry
    _app_state["start_time"] = time.time()
    _app_state["settings"] = settings

    logger.info("Service initialized successfully")
    yield

    # Shutdown
    logger.info("Shutting down service...")
    await engine.unload()
    _app_state.clear()


app = FastAPI(
    title="TraceAI Inference Service",
    version="0.1.0",
    description="GPT-2 inference with runtime controls for LADC 2026",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        uptime_seconds=time.time() - _app_state.get("start_time", time.time()),
    )


@app.get("/ready")
async def ready():
    """Readiness probe."""
    engine: InferenceEngine = _app_state.get("engine")
    if engine is None or not engine.is_loaded:
        raise HTTPException(status_code=503, detail="Model not loaded")
    controls: ControlsManager = _app_state.get("controls")
    if controls and controls.is_circuit_open():
        raise HTTPException(status_code=503, detail="Circuit breaker open")
    return {"ready": True}


@app.get("/metrics/snapshot")
async def metrics_snapshot():
    """Return current telemetry snapshot."""
    telemetry: TelemetryCollector = _app_state.get("telemetry")
    if telemetry is None:
        raise HTTPException(status_code=503, detail="Telemetry not initialized")
    return telemetry.snapshot()


@app.get("/configuration", response_model=ConfigurationResponse)
async def configuration():
    """Return current service configuration with digest."""
    controls: ControlsManager = _app_state.get("controls")
    engine: InferenceEngine = _app_state.get("engine")
    settings = _app_state.get("settings")

    config_data = {
        "max_new_tokens": controls.max_new_tokens,
        "timeout_seconds": controls.timeout_seconds,
        "max_concurrency": controls.max_concurrency,
        "queue_depth": controls.queue_depth,
        "rate_limit_rpm": controls.rate_limit_rpm,
        "circuit_breaker_enabled": controls.circuit_breaker_enabled,
        "model_id": settings.model_id if settings else "unknown",
        "device": engine.device if engine else "unknown",
    }

    return ConfigurationResponse(
        **config_data,
        configuration_digest=hash_json(config_data),
    )


class UpdateConfigRequest(BaseModel):
    """Request body for runtime configuration update."""
    max_new_tokens: Optional[int] = None
    timeout_seconds: Optional[float] = None
    max_concurrency: Optional[int] = None
    queue_depth: Optional[int] = None
    rate_limit_rpm: Optional[int] = None
    circuit_breaker_enabled: Optional[bool] = None


@app.put("/configuration")
async def update_configuration(req: UpdateConfigRequest):
    """Update runtime configuration (for experimental campaigns)."""
    controls: ControlsManager = _app_state.get("controls")
    if controls is None:
        raise HTTPException(status_code=503, detail="Controls not initialized")

    changes = controls.update_configuration(
        max_new_tokens=req.max_new_tokens,
        timeout_seconds=req.timeout_seconds,
        max_concurrency=req.max_concurrency,
        queue_depth=req.queue_depth,
        rate_limit_rpm=req.rate_limit_rpm,
    )

    # Handle circuit_breaker_enabled toggle
    if req.circuit_breaker_enabled is not None:
        if req.circuit_breaker_enabled and controls.circuit_breaker_threshold == 0:
            controls.circuit_breaker_threshold = 5
            changes["circuit_breaker_enabled"] = {"old": False, "new": True}
        elif not req.circuit_breaker_enabled and controls.circuit_breaker_threshold > 0:
            controls.circuit_breaker_threshold = 0
            changes["circuit_breaker_enabled"] = {"old": True, "new": False}

    # Reset rate limiter and circuit breaker state on config change
    controls.reset()

    return {"updated": True, "changes": changes}


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, request: Request):
    """Generate text from a prompt."""
    controls: ControlsManager = _app_state.get("controls")
    engine: InferenceEngine = _app_state.get("engine")
    queue: RequestQueue = _app_state.get("queue")
    telemetry: TelemetryCollector = _app_state.get("telemetry")
    settings = _app_state.get("settings")

    # Check circuit breaker
    if controls.is_circuit_open():
        raise HTTPException(status_code=503, detail="Circuit breaker open")

    # Check rate limit
    client_ip = request.client.host if request.client else "unknown"
    if not controls.check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Check queue depth
    if not queue.try_enqueue():
        raise HTTPException(status_code=503, detail="Queue full")

    request_id = req.request_id or f"req-{int(time.time()*1000)}"
    start = time.time()

    try:
        max_tokens = min(
            req.max_new_tokens or controls.max_new_tokens,
            controls.max_new_tokens,
        )

        result = await asyncio.wait_for(
            engine.generate(
                prompt=req.prompt,
                max_new_tokens=max_tokens,
                temperature=req.temperature,
                seed=req.seed,
            ),
            timeout=controls.timeout_seconds,
        )

        latency_ms = (time.time() - start) * 1000
        controls.record_success()

        # Collect telemetry
        telemetry.record_request(latency_ms, result["tokens_generated"])

        config_data = {
            "max_new_tokens": controls.max_new_tokens,
            "timeout_seconds": controls.timeout_seconds,
            "max_concurrency": controls.max_concurrency,
            "queue_depth": controls.queue_depth,
            "rate_limit_rpm": controls.rate_limit_rpm,
            "circuit_breaker_enabled": controls.circuit_breaker_enabled,
            "model_id": settings.model_id if settings else "unknown",
            "device": engine.device,
        }

        return GenerateResponse(
            request_id=request_id,
            text=result["text"],
            tokens_generated=result["tokens_generated"],
            latency_ms=latency_ms,
            model_id=settings.model_id if settings else "unknown",
            configuration_digest=hash_json(config_data),
        )

    except asyncio.TimeoutError:
        controls.record_failure()
        raise HTTPException(status_code=504, detail="Generation timeout")
    except Exception as e:
        controls.record_failure()
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail="Internal error")
    finally:
        queue.dequeue()


def start_server(host: str = "127.0.0.1", port: int = 8000, profile: str = "local"):
    """Start the uvicorn server."""
    import uvicorn

    # Set profile before starting
    import os
    os.environ.setdefault("TRACEAI_PROFILE", profile)

    uvicorn.run(
        "traceai.service.app:app",
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )
