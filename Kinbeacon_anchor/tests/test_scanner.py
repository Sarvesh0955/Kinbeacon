import os
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from ble.scanner import BLEScanner, start_scanner_thread
from db.store import SignalStore


def make_mock_advertisement(name=None, rssi=-60, manufacturer_data=None):
    adv_data = MagicMock(spec=AdvertisementData)
    adv_data.local_name = name
    adv_data.rssi = rssi
    adv_data.manufacturer_data = manufacturer_data or {}

    device = MagicMock(spec=BLEDevice)
    device.name = name
    device.address = "00:11:22:33:44:55"
    return device, adv_data


class TestBLEScanner(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_scanner.db")
        self.store = SignalStore(db_path=self.db_path)
        self.store.init_db()

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_extended_full_json_framing(self):
        """Tests parsing Extended Full JSON (32B): {"device_id":"kb-1234567890abcdef"} in 0xFFFF"""
        scanner = BLEScanner(store=self.store, device_prefix="kb-", company_id=0xFFFF)
        payload = b'{"device_id":"kb-1234567890abcdef"}'
        device, adv = make_mock_advertisement(
            name=None, rssi=-52, manufacturer_data={0xFFFF: payload}
        )

        record_id = scanner.handle_advertisement(device, adv)
        self.assertIsNotNone(record_id)
        records = self.store.query_device("kb-1234567890abcdef", since_minutes=15)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["rssi"], -52)

    def test_compact_kv_framing(self):
        """Tests parsing Compact KV (19B): kb-1234567890abcdef in 0xFFFF"""
        scanner = BLEScanner(store=self.store, device_prefix="kb-", company_id=0xFFFF)
        payload = b"kb-1234567890abcdef"
        device, adv = make_mock_advertisement(
            name=None, rssi=-58, manufacturer_data={0xFFFF: payload}
        )

        record_id = scanner.handle_advertisement(device, adv)
        self.assertIsNotNone(record_id)
        records = self.store.query_device("kb-1234567890abcdef", since_minutes=15)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["rssi"], -58)

    def test_legacy_json_base64_framing(self):
        """Tests parsing Legacy JSON Base64: {"device_id":"kb-aGVsYXNka2pm"} in 0xFFFF"""
        scanner = BLEScanner(store=self.store, device_prefix="kb-", company_id=0xFFFF)
        payload = b'{"device_id":"kb-aGVsYXNka2pm"}'
        device, adv = make_mock_advertisement(
            name=None, rssi=-64, manufacturer_data={0xFFFF: payload}
        )

        record_id = scanner.handle_advertisement(device, adv)
        self.assertIsNotNone(record_id)
        records = self.store.query_device("kb-aGVsYXNka2pm", since_minutes=15)
        self.assertEqual(len(records), 1)

    def test_local_name_fallback(self):
        """Tests fallback to advertised local_name when manufacturer data is absent"""
        scanner = BLEScanner(store=self.store, device_prefix="kb-")
        device, adv = make_mock_advertisement(name="kb-phone1", rssi=-55)

        record_id = scanner.handle_advertisement(device, adv)
        self.assertIsNotNone(record_id)
        records = self.store.query_device("kb-phone1", since_minutes=15)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["rssi"], -55)

    def test_handle_advertisement_mismatched_prefix_ignored(self):
        scanner = BLEScanner(store=self.store, device_prefix="kb-")
        device, adv = make_mock_advertisement(name="AirPods-Pro", rssi=-40)

        record_id = scanner.handle_advertisement(device, adv)
        self.assertIsNone(record_id)
        stats = self.store.get_stats()
        self.assertEqual(stats["total_records"], 0)

    def test_handle_advertisement_empty_name_and_mfg_ignored(self):
        scanner = BLEScanner(store=self.store, device_prefix="kb-")
        device, adv = make_mock_advertisement(name=None, rssi=-70)

        record_id = scanner.handle_advertisement(device, adv)
        self.assertIsNone(record_id)

    def test_handle_advertisement_fallback_rssi(self):
        scanner = BLEScanner(store=self.store, device_prefix="kb-")
        device, adv = make_mock_advertisement(name="kb-test", rssi=None)

        record_id = scanner.handle_advertisement(device, adv)
        self.assertIsNotNone(record_id)

        records = self.store.query_device("kb-test", since_minutes=15)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["rssi"], -100)


if __name__ == "__main__":
    unittest.main()
