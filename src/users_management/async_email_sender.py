from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor

logger = logging.getLogger(__name__)


class EmailQueueFullError(RuntimeError):
    pass


class AsyncEmailSender:
    """Bounded asynchronous decorator for an email sender adapter."""

    def __init__(self, sender, max_workers: int = 4, max_queue_size: int = 100):
        if max_workers < 1 or max_queue_size < 1:
            raise ValueError("max_workers and max_queue_size must be positive")
        self.sender = sender
        self.executor = ThreadPoolExecutor(max_workers=max_workers,
                                           thread_name_prefix="email-notification")
        # The queue can hold max_queue_size waiting tasks in addition to active workers.
        self.capacity = threading.BoundedSemaphore(max_workers + max_queue_size)

    def send(self, to: str, subject: str, body: str) -> Future:
        if not self.capacity.acquire(blocking=False):
            raise EmailQueueFullError("Email notification queue is full")
        try:
            future = self.executor.submit(self.sender.send, to, subject, body)
        except Exception:
            self.capacity.release()
            raise
        future.add_done_callback(self._finish)
        return future

    def _finish(self, future: Future) -> None:
        self.capacity.release()
        error = future.exception()
        if error is not None:
            logger.error("Asynchronous email delivery failed: %s", error)

    def shutdown(self, wait: bool = True) -> None:
        self.executor.shutdown(wait=wait, cancel_futures=False)
