"""System and GPU telemetry collection."""

import time
from typing import Any, Optional

import psutil

from traceai.logging_config import get_logger

logger = get_logger("service.telemetry")


class TelemetryCollector:
    """Collects CPU, RAM, and GPU telemetry metrics."""

    def __init__(self):
        self._request_count = 0
        self._total_latency_ms = 0.0
        self._total_tokens = 0
        self._start_time = time.time()
        self._gpu_available = False
        self._pynvml_handle = None

        self._try_init_gpu()

    def _try_init_gpu(self) -> None:
        """Try to initialize GPU monitoring via pynvml."""
        try:
            import pynvml
            pynvml.nvmlInit()
            self._pynvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._gpu_available = True
            logger.info("GPU telemetry initialized via pynvml")
        except (ImportError, Exception) as e:
            self._gpu_available = False
            logger.debug(f"GPU telemetry not available: {e}")

    def record_request(self, latency_ms: float, tokens_generated: int) -> None:
        """Record metrics from a completed request."""
        self._request_count += 1
        self._total_latency_ms += latency_ms
        self._total_tokens += tokens_generated

    def snapshot(self) -> dict[str, Any]:
        """Capture current system telemetry snapshot."""
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()

        snap: dict[str, Any] = {
            "timestamp": time.time(),
            "uptime_seconds": time.time() - self._start_time,
            "cpu_percent": cpu_percent,
            "ram_used_mb": round(memory.used / (1024**2), 1),
            "ram_total_mb": round(memory.total / (1024**2), 1),
            "ram_percent": memory.percent,
            "request_count": self._request_count,
            "avg_latency_ms": (
                self._total_latency_ms / self._request_count
                if self._request_count > 0
                else 0.0
            ),
            "total_tokens_generated": self._total_tokens,
            "gpu": self._get_gpu_metrics(),
        }

        return snap

    def _get_gpu_metrics(self) -> dict[str, Any]:
        """Get GPU metrics if available."""
        if not self._gpu_available or self._pynvml_handle is None:
            return {
                "available": False,
                "utilization_percent": None,
                "memory_used_mb": None,
                "memory_total_mb": None,
                "temperature_c": None,
                "power_w": None,
            }

        try:
            import pynvml

            util = pynvml.nvmlDeviceGetUtilizationRates(self._pynvml_handle)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(self._pynvml_handle)
            temp = pynvml.nvmlDeviceGetTemperature(
                self._pynvml_handle, pynvml.NVML_TEMPERATURE_GPU
            )
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(self._pynvml_handle) / 1000.0
            except pynvml.NVMLError:
                power = None

            return {
                "available": True,
                "utilization_percent": util.gpu,
                "memory_used_mb": round(mem_info.used / (1024**2), 1),
                "memory_total_mb": round(mem_info.total / (1024**2), 1),
                "temperature_c": temp,
                "power_w": power,
            }
        except Exception as e:
            logger.debug(f"GPU metrics collection error: {e}")
            return {
                "available": False,
                "utilization_percent": None,
                "memory_used_mb": None,
                "memory_total_mb": None,
                "temperature_c": None,
                "power_w": None,
            }

    def get_system_metrics(self) -> dict[str, Any]:
        """Get current system metrics for request observation."""
        memory = psutil.virtual_memory()
        metrics = {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_mb": round(memory.used / (1024**2), 1),
        }

        if self._gpu_available:
            gpu = self._get_gpu_metrics()
            metrics["gpu_utilization_percent"] = gpu.get("utilization_percent")
            metrics["gpu_memory_mb"] = gpu.get("memory_used_mb")
            metrics["gpu_temperature_c"] = gpu.get("temperature_c")
            metrics["gpu_power_w"] = gpu.get("power_w")

        return metrics
