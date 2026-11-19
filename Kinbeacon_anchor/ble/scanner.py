import asyncio
import json
import re
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
    Filters devices by Manufacturer Data (Company ID 0xFFFF / 65535) or local name,
    supporting Compact KV, Extended Full JSON, and Legacy JSON framing modes.
    """

    def __init__(
        self,
        store: SignalStore,
        device_prefix: str = config.DEVICE_PREFIX,
        company_id: int = config.COMPANY_ID,
        retry_interval: int = config.BLE_RETRY_INTERVAL_SECONDS,
    ):
        self.store = store
        self.device_prefix = device_prefix
        self.company_id = company_id
        self.retry_interval = retry_interval
        self.is_running = False
        self.signals_received = 0

    def parse_payload(self, raw_bytes: bytes) -> Optional[str]:
        """
        Parses device_id from manufacturer data payload bytes.
        Supports:
        - Extended Full JSON: b'{"device_id":"kb-<16-hex-chars>"}'
        - Legacy JSON Base64: b'{"device_id":"kb-<b64>"}'
        - Compact KV: b'kb-<16-hex-chars>'
        """
        if not raw_bytes:
            return None

        raw_str = raw_bytes.decode("utf-8", errors="ignore").strip("\x00 \r\n")

        # 1. Try parsing JSON payload
        if "{" in raw_str:
            try:
                data = json.loads(raw_str)
                if isinstance(data, dict) and "device_id" in data:
                    candidate = str(data["device_id"]).strip()
                    if not self.device_prefix or candidate.startswith(self.device_prefix):
                        return candidate
            except Exception:
                # Truncated or malformed JSON fallback via regex
                m = re.search(r'"device_id"\s*:\s*"([^"]+)"', raw_str)
                if m:
                    candidate = m.group(1).strip()
                    if not self.device_prefix or candidate.startswith(self.device_prefix):
                        return candidate

        # 2. Try raw string / compact KV
        if self.device_prefix:
            m = re.search(rf"({re.escape(self.device_prefix)}[a-zA-Z0-9_\-]+)", raw_str)
            if m:
                return m.group(1).strip()
        elif raw_str:
            return raw_str.strip()

        return None

    def extract_device_id(
        self, device: BLEDevice, advertisement_data: AdvertisementData
    ) -> Optional[str]:
        """
        Extracts device_id from:
        1. Manufacturer Specific Data (0xFFFF / 65535, or any present company ID)
        2. Advertisement local_name or device.name
        """
        # 1. Check Manufacturer Specific Data
        if advertisement_data.manufacturer_data:
            # Check configured company ID (default 0xFFFF = 65535)
            if self.company_id in advertisement_data.manufacturer_data:
                mfg_data = advertisement_data.manufacturer_data[self.company_id]
                dev_id = self.parse_payload(mfg_data)
                if dev_id:
                    return dev_id

            # Fallback: inspect any other company IDs present
            for comp_id, mfg_data in advertisement_data.manufacturer_data.items():
                dev_id = self.parse_payload(mfg_data)
                if dev_id:
                    return dev_id

        # 2. Check local name / device name
        raw_name = advertisement_data.local_name or device.name
        if raw_name:
            clean_name = raw_name.strip()
            if not self.device_prefix or clean_name.startswith(self.device_prefix):
                return clean_name

        return None

    def handle_advertisement(
        self, device: BLEDevice, advertisement_data: AdvertisementData
    ) -> Optional[int]:
        """
        Process a single BLE advertisement event.
        Returns the inserted record ID if matched and stored, None otherwise.
        """
        device_id = self.extract_device_id(device, advertisement_data)
        if not device_id:
            return None

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
            "Initializing BLE scanner (prefix filter: '%s', company ID: 0x%04X)...",
            self.device_prefix or "<ALL>",
            self.company_id,
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
    company_id: int = config.COMPANY_ID,
) -> Tuple[threading.Thread, BLEScanner]:
    """
    Launches BLEScanner on a dedicated background thread with its own asyncio event loop.
    Returns (thread, scanner_instance).
    """
    scanner = BLEScanner(
        store=store, device_prefix=device_prefix, company_id=company_id
    )

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
