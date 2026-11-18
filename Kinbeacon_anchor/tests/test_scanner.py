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


def make_mock_advertisement(name=None, rssi=-60):
    adv_data = MagicMock(spec=AdvertisementData)
    adv_data.local_name = name
    adv_data.rssi = rssi

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

    def test_handle_advertisement_matching_prefix(self):
        scanner = BLEScanner(store=self.store, device_prefix="KINBEACON-")
        device, adv = make_mock_advertisement(name="KINBEACON-PHONE1", rssi=-55)

        record_id = scanner.handle_advertisement(device, adv)
        self.assertIsNotNone(record_id)
        self.assertEqual(scanner.signals_received, 1)

        # Check DB
        records = self.store.query_device("KINBEACON-PHONE1", since_minutes=15)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["rssi"], -55)

    def test_handle_advertisement_mismatched_prefix_ignored(self):
        scanner = BLEScanner(store=self.store, device_prefix="KINBEACON-")
        device, adv = make_mock_advertisement(name="AirPods-Pro", rssi=-40)

        record_id = scanner.handle_advertisement(device, adv)
        self.assertIsNone(record_id)
        self.assertEqual(scanner.signals_received, 0)

        # DB remains empty
        stats = self.store.get_stats()
        self.assertEqual(stats["total_records"], 0)

    def test_handle_advertisement_empty_name_ignored(self):
        scanner = BLEScanner(store=self.store, device_prefix="KINBEACON-")
        device, adv = make_mock_advertisement(name=None, rssi=-70)

        record_id = scanner.handle_advertisement(device, adv)
        self.assertIsNone(record_id)
        self.assertEqual(scanner.signals_received, 0)

    def test_handle_advertisement_fallback_rssi(self):
        scanner = BLEScanner(store=self.store, device_prefix="KINBEACON-")
        device, adv = make_mock_advertisement(name="KINBEACON-TEST", rssi=None)

        record_id = scanner.handle_advertisement(device, adv)
        self.assertIsNotNone(record_id)

        records = self.store.query_device("KINBEACON-TEST", since_minutes=15)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["rssi"], -100)

    def test_handle_advertisement_empty_prefix_accepts_all(self):
        scanner = BLEScanner(store=self.store, device_prefix="")
        device, adv = make_mock_advertisement(name="ANY-DEVICE-123", rssi=-62)

        record_id = scanner.handle_advertisement(device, adv)
        self.assertIsNotNone(record_id)
        self.assertEqual(scanner.signals_received, 1)

        records = self.store.query_device("ANY-DEVICE-123", since_minutes=15)
        self.assertEqual(len(records), 1)


if __name__ == "__main__":
    unittest.main()
