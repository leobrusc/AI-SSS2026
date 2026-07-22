"""Bounded request queue for the inference service."""

from threading import Lock

from traceai.logging_config import get_logger

logger = get_logger("service.queueing")


class RequestQueue:
    """Thread-safe bounded queue for managing concurrent requests."""

    def __init__(self, max_depth: int = 16):
        self.max_depth = max_depth
        self._current_depth = 0
        self._lock = Lock()
        self._total_enqueued = 0
        self._total_rejected = 0

    @property
    def current_depth(self) -> int:
        """Current number of requests in the queue."""
        return self._current_depth

    @property
    def is_full(self) -> bool:
        """Whether the queue is at capacity."""
        return self._current_depth >= self.max_depth

    def try_enqueue(self) -> bool:
        """Attempt to enqueue a request. Returns True if successful."""
        with self._lock:
            if self._current_depth >= self.max_depth:
                self._total_rejected += 1
                logger.warning(
                    f"Queue full ({self._current_depth}/{self.max_depth}), "
                    f"rejecting request"
                )
                return False
            self._current_depth += 1
            self._total_enqueued += 1
            return True

    def dequeue(self) -> None:
        """Mark a request as completed, freeing queue space."""
        with self._lock:
            if self._current_depth > 0:
                self._current_depth -= 1

    def stats(self) -> dict:
        """Return queue statistics."""
        with self._lock:
            return {
                "current_depth": self._current_depth,
                "max_depth": self.max_depth,
                "total_enqueued": self._total_enqueued,
                "total_rejected": self._total_rejected,
                "utilization": self._current_depth / self.max_depth if self.max_depth > 0 else 0,
            }

    def reset(self) -> None:
        """Reset queue state."""
        with self._lock:
            self._current_depth = 0
            self._total_enqueued = 0
            self._total_rejected = 0
