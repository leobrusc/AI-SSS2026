"""Runtime controls: rate limiting, circuit breaker, concurrency management."""

import time
from collections import defaultdict
from threading import Lock
from typing import Optional

from traceai.logging_config import get_logger

logger = get_logger("service.controls")


class ControlsManager:
    """Manages runtime controls for the inference service."""

    def __init__(
        self,
        max_new_tokens: int = 100,
        timeout_seconds: float = 30.0,
        max_concurrency: int = 4,
        queue_depth: int = 16,
        rate_limit_rpm: int = 120,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: float = 30.0,
    ):
        self.max_new_tokens = max_new_tokens
        self.timeout_seconds = timeout_seconds
        self.max_concurrency = max_concurrency
        self.queue_depth = queue_depth
        self.rate_limit_rpm = rate_limit_rpm
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout

        # Circuit breaker state
        self._failure_count = 0
        self._circuit_open_since: Optional[float] = None
        self._circuit_lock = Lock()

        # Rate limiter state
        self._request_timestamps: dict[str, list[float]] = defaultdict(list)
        self._rate_lock = Lock()

    @property
    def circuit_breaker_enabled(self) -> bool:
        """Whether circuit breaker is enabled."""
        return self.circuit_breaker_threshold > 0

    def is_circuit_open(self) -> bool:
        """Check if the circuit breaker is currently open."""
        if not self.circuit_breaker_enabled:
            return False

        with self._circuit_lock:
            if self._circuit_open_since is None:
                return False

            elapsed = time.time() - self._circuit_open_since
            if elapsed >= self.circuit_breaker_timeout:
                # Half-open: allow one request through
                logger.info("Circuit breaker transitioning to half-open")
                self._circuit_open_since = None
                self._failure_count = 0
                return False

            return True

    def record_success(self) -> None:
        """Record a successful request."""
        with self._circuit_lock:
            self._failure_count = 0
            if self._circuit_open_since is not None:
                logger.info("Circuit breaker closed after successful request")
                self._circuit_open_since = None

    def record_failure(self) -> None:
        """Record a failed request and potentially open the circuit."""
        if not self.circuit_breaker_enabled:
            return

        with self._circuit_lock:
            self._failure_count += 1
            if self._failure_count >= self.circuit_breaker_threshold:
                if self._circuit_open_since is None:
                    self._circuit_open_since = time.time()
                    logger.warning(
                        f"Circuit breaker OPEN after {self._failure_count} failures"
                    )

    def check_rate_limit(self, client_id: str) -> bool:
        """Check if a client is within rate limits. Returns True if allowed."""
        if self.rate_limit_rpm <= 0:
            return True

        now = time.time()
        window = 60.0  # 1 minute window

        with self._rate_lock:
            timestamps = self._request_timestamps[client_id]
            # Remove old timestamps
            self._request_timestamps[client_id] = [
                t for t in timestamps if now - t < window
            ]
            timestamps = self._request_timestamps[client_id]

            if len(timestamps) >= self.rate_limit_rpm:
                return False

            timestamps.append(now)
            return True

    def reset(self) -> None:
        """Reset all controls state."""
        with self._circuit_lock:
            self._failure_count = 0
            self._circuit_open_since = None
        with self._rate_lock:
            self._request_timestamps.clear()

    def update_configuration(
        self,
        max_new_tokens: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        max_concurrency: Optional[int] = None,
        queue_depth: Optional[int] = None,
        rate_limit_rpm: Optional[int] = None,
    ) -> dict[str, any]:
        """Update runtime configuration. Returns dict of changes."""
        changes = {}
        if max_new_tokens is not None and max_new_tokens != self.max_new_tokens:
            changes["max_new_tokens"] = {"old": self.max_new_tokens, "new": max_new_tokens}
            self.max_new_tokens = max_new_tokens
        if timeout_seconds is not None and timeout_seconds != self.timeout_seconds:
            changes["timeout_seconds"] = {"old": self.timeout_seconds, "new": timeout_seconds}
            self.timeout_seconds = timeout_seconds
        if max_concurrency is not None and max_concurrency != self.max_concurrency:
            changes["max_concurrency"] = {"old": self.max_concurrency, "new": max_concurrency}
            self.max_concurrency = max_concurrency
        if queue_depth is not None and queue_depth != self.queue_depth:
            changes["queue_depth"] = {"old": self.queue_depth, "new": queue_depth}
            self.queue_depth = queue_depth
        if rate_limit_rpm is not None and rate_limit_rpm != self.rate_limit_rpm:
            changes["rate_limit_rpm"] = {"old": self.rate_limit_rpm, "new": rate_limit_rpm}
            self.rate_limit_rpm = rate_limit_rpm

        if changes:
            logger.info(f"Configuration updated: {list(changes.keys())}")
        return changes

    def get_configuration_dict(self) -> dict:
        """Return current configuration as a dictionary."""
        return {
            "max_new_tokens": self.max_new_tokens,
            "timeout_seconds": self.timeout_seconds,
            "max_concurrency": self.max_concurrency,
            "queue_depth": self.queue_depth,
            "rate_limit_rpm": self.rate_limit_rpm,
            "circuit_breaker_threshold": self.circuit_breaker_threshold,
            "circuit_breaker_timeout": self.circuit_breaker_timeout,
            "circuit_breaker_enabled": self.circuit_breaker_enabled,
        }
