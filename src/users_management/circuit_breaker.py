from __future__ import annotations

import threading
import time
from collections import deque


class CircuitOpenError(RuntimeError):
    """Raised while the circuit breaker is open."""


class CircuitBreaker:
    def __init__(self, failure_threshold: float = 50.0, window_size: int = 10,
                 minimum_calls: int = 5, open_duration: float = 30.0,
                 clock=time.monotonic):
        if not 0 < failure_threshold <= 100:
            raise ValueError("failure_threshold must be in (0, 100]")
        if window_size < 1 or minimum_calls < 1 or minimum_calls > window_size:
            raise ValueError("minimum_calls must be between 1 and window_size")
        self.failure_threshold = failure_threshold
        self.minimum_calls = minimum_calls
        self.open_duration = open_duration
        self.clock = clock
        self.results: deque[bool] = deque(maxlen=window_size)
        self.opened_at: float | None = None
        self._lock = threading.Lock()

    def before_call(self) -> None:
        with self._lock:
            if self.opened_at is None:
                return
            if self.clock() - self.opened_at < self.open_duration:
                raise CircuitOpenError("Brevo circuit breaker is open")
            self.opened_at = None
            self.results.clear()

    def record_success(self) -> None:
        self._record(True)

    def record_failure(self) -> None:
        self._record(False)

    def _record(self, succeeded: bool) -> None:
        with self._lock:
            self.results.append(succeeded)
            if len(self.results) < self.minimum_calls:
                return
            failure_rate = 100 * (len(self.results) - sum(self.results)) / len(self.results)
            if failure_rate >= self.failure_threshold:
                self.opened_at = self.clock()
