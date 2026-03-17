"""
HeartbeatStream – keeps an NDJSON stream alive during idle periods.

Wraps any source iterator and injects heartbeat dicts when the source
has not yielded a chunk within ``interval`` seconds.

Thread model
------------
* A **producer thread** (daemon) drains the source iterator into a
  thread-safe ``queue.Queue``, tagging each item as ``("data", item)``.
* The **main thread** (Flask response writer) calls ``queue.get(timeout)``
  in ``__next__``.  A timeout means the source was idle → return a
  heartbeat dict.  Real data is returned as-is.

Lifecycle / cleanup
-------------------
* Normal completion  → producer puts ``_END`` sentinel → ``StopIteration``.
* Source exception    → producer puts ``("error", e)`` → re-raised in main.
* Client disconnect   → Flask throws ``GeneratorExit`` into the outer
  generator, which must call ``close()``.  This sets ``_stop``; the
  producer thread notices on its next iteration, breaks, and calls
  ``source.close()`` **in its own thread** so that ``GeneratorExit``
  propagates correctly through ``ForegroundSessionRunner.stream()`` cleanup.
"""

import logging
import queue
import threading
from typing import Any, Callable, Dict, Iterator, Optional

logger = logging.getLogger(__name__)

# Sentinels – identity-compared, never leaked outside the class.
_END = object()

# Default heartbeat interval in seconds.
DEFAULT_HEARTBEAT_INTERVAL_SEC = 15.0


def _default_heartbeat() -> Dict[str, str]:
    return {"type": "heartbeat"}


class HeartbeatStream:
    """Iterator wrapper that injects heartbeat dicts during idle periods."""

    def __init__(
        self,
        source: Iterator[Any],
        interval: float = DEFAULT_HEARTBEAT_INTERVAL_SEC,
        heartbeat_factory: Optional[Callable[[], Dict]] = None,
    ) -> None:
        self._source = source
        self._interval = interval
        self._heartbeat_factory = heartbeat_factory or _default_heartbeat
        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()

        self._producer = threading.Thread(
            target=self._consume_source,
            name="heartbeat-producer",
            daemon=True,
        )
        self._producer.start()

    # ── producer (background thread) ──────────────────────────

    def _consume_source(self) -> None:
        """Drain the source iterator into the queue, then clean up."""
        try:
            for item in self._source:
                if self._stop.is_set():
                    break
                self._queue.put(("data", item))
        except Exception as e:
            if not self._stop.is_set():
                self._queue.put(("error", e))
        finally:
            # Close the source generator in *this* thread so that
            # GeneratorExit propagates correctly through the
            # ForegroundSessionRunner.stream() → lifecycle.complete / fail chain.
            if hasattr(self._source, "close"):
                try:
                    self._source.close()
                except Exception:
                    logger.debug("Error closing source iterator", exc_info=True)
            self._queue.put((_END, None))

    # ── consumer (main / Flask thread) ────────────────────────

    def __iter__(self) -> "HeartbeatStream":
        return self

    def __next__(self) -> Any:
        while True:
            try:
                tag, value = self._queue.get(timeout=self._interval)
            except queue.Empty:
                # No data for `interval` seconds → heartbeat
                return self._heartbeat_factory()

            if tag is _END:
                raise StopIteration
            if tag == "error":
                raise value
            return value  # tag == "data"

    # ── teardown (called on client disconnect) ────────────────

    def close(self) -> None:
        """Signal the producer to stop.  Thread-safe."""
        self._stop.set()
