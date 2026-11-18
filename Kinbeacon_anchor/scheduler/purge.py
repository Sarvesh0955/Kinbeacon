import threading
from typing import Optional

import config
from db.store import SignalStore
from utils.logging_config import setup_logger

logger = setup_logger("scheduler.purge")


class PurgeScheduler:
    """
    Background worker that periodically deletes records older than RETENTION_MINUTES.
    Runs continuously until stop() is invoked.
    """

    def __init__(
        self,
        store: SignalStore,
        retention_minutes: int = config.RETENTION_MINUTES,
        interval_seconds: int = config.PURGE_INTERVAL_SECONDS,
    ):
        self.store = store
        self.retention_minutes = retention_minutes
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Starts the background purging thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("PurgeScheduler is already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop, name="PurgeSchedulerThread", daemon=True
        )
        self._thread.start()
        logger.info(
            "PurgeScheduler started (retention: %d mins, interval: %d s).",
            self.retention_minutes,
            self.interval_seconds,
        )

    def _run_loop(self) -> None:
        """Periodic loop executing database purge."""
        while not self._stop_event.is_set():
            # Wait for interval_seconds, wakes up immediately if stopped
            if self._stop_event.wait(timeout=self.interval_seconds):
                break

            try:
                self.store.purge_old(retention_minutes=self.retention_minutes)
            except Exception as exc:
                logger.error("Error during scheduled retention purge: %s", exc)

    def stop(self, timeout: float = 2.0) -> None:
        """Signals the scheduler to stop and joins the thread."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            logger.info("PurgeScheduler stopped.")
        self._thread = None
