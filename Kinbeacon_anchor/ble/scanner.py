import asyncio
import threading
from typing import Optional, Tuple

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

import config
from db.store import SignalStore
from utils.logging_config import setup_logger

logger = setup_logger("ble.scanner")


class BLEScanner:
    """
    Continuous BLE advertisement scanner.
    Filters devices by configured prefix, extracts RSSI and timestamp,
    and inserts records into SignalStore.
    """

    def __init__(
        self,
        store: SignalStore,
        device_prefix: str = config.DEVICE_PREFIX,
        retry_interval: int = config.BLE_RETRY_INTERVAL_SECONDS,
    ):
        self.store = store
        self.device_prefix = device_prefix
        self.retry_interval = retry_interval
        self.is_running = False
        self.signals_received = 0

    def handle_advertisement(
        self, device: BLEDevice, advertisement_data: AdvertisementData
    ) -> Optional[int]:
        """
        Process a single BLE advertisement event.
        Returns the inserted record ID if matched and stored, None otherwise.
        """
        raw_name = advertisement_data.local_name or device.name
        if not raw_name:
            return None

        clean_name = raw_name.strip()

        # Filter by device_prefix if configured
        if self.device_prefix and not clean_name.startswith(self.device_prefix):
            return None

        device_id = clean_name
        rssi = advertisement_data.rssi
        if rssi is None:
            rssi = -100

        record_id = self.store.insert_signal(device_id=device_id, rssi=rssi)
        self.signals_received += 1
        logger.info(
            "Detected '%s' | RSSI: %d dBm | Total captured: %d",
            device_id,
            rssi,
            self.signals_received,
        )
        return record_id

    async def run(self, stop_event: threading.Event) -> None:
        """
        Continuous async scanning loop with auto-reconnection and graceful shutdown.
        """
        logger.info(
            "Initializing BLE scanner (prefix filter: '%s')...",
            self.device_prefix or "<ALL>",
        )
        self.is_running = True

        try:
            while not stop_event.is_set():
                try:
                    async with BleakScanner(
                        detection_callback=self.handle_advertisement
                    ) as scanner:
                        logger.info("BLE Scanner active and listening for advertisements...")
                        while not stop_event.is_set():
                            await asyncio.sleep(0.5)
                except Exception as exc:
                    if stop_event.is_set():
                        break
                    logger.error(
                        "BLE Scanner encountered an error: %s. Reconnecting in %d seconds...",
                        exc,
                        self.retry_interval,
                    )
                    # Backoff sleep while honoring stop_event
                    for _ in range(self.retry_interval * 2):
                        if stop_event.is_set():
                            break
                        await asyncio.sleep(0.5)
        finally:
            self.is_running = False
            logger.info("BLE Scanner stopped cleanly.")


def start_scanner_thread(
    store: SignalStore,
    stop_event: threading.Event,
    device_prefix: str = config.DEVICE_PREFIX,
) -> Tuple[threading.Thread, BLEScanner]:
    """
    Launches BLEScanner on a dedicated background thread with its own asyncio event loop.
    Returns (thread, scanner_instance).
    """
    scanner = BLEScanner(store=store, device_prefix=device_prefix)

    def _worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(scanner.run(stop_event))
        finally:
            loop.close()

    thread = threading.Thread(target=_worker, name="BLEScannerThread", daemon=True)
    thread.start()
    return thread, scanner
