import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from api.routes import create_app
from ble.scanner import BLEScanner
from db.store import SignalStore
from scheduler.purge import PurgeScheduler


class TestEndToEndPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_e2e.db")
        self.store = SignalStore(db_path=self.db_path)
        self.store.init_db()

        self.scanner = BLEScanner(store=self.store, device_prefix="KINBEACON-")
        self.scheduler = PurgeScheduler(
            store=self.store, retention_minutes=15, interval_seconds=0.1
        )
        self.scheduler.start()

        self.app = create_app(
            store=self.store, scanner=self.scanner, anchor_id="TEST-ANCHOR-E2E"
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.scheduler.stop()
        self.store.close()
        self.temp_dir.cleanup()

    def _simulate_ble_packet(self, name: str, rssi: int):
        adv = MagicMock(spec=AdvertisementData)
        adv.local_name = name
        adv.rssi = rssi

        dev = MagicMock(spec=BLEDevice)
        dev.name = name
        return self.scanner.handle_advertisement(dev, adv)

    def test_full_pipeline_ingest_query_and_purge(self):
        # 1. Simulate incoming BLE advertisements from Phone 1
        rec1 = self._simulate_ble_packet("KINBEACON-PHONE1", -58)
        rec2 = self._simulate_ble_packet("KINBEACON-PHONE1", -61)
        self.assertIsNotNone(rec1)
        self.assertIsNotNone(rec2)

        # 2. Simulate incoming BLE advertisements from Phone 2
        rec3 = self._simulate_ble_packet("KINBEACON-PHONE2", -75)
        self.assertIsNotNone(rec3)

        # 3. Simulate another non-kinbeacon device (e.g. mouse or TV)
        rec_ignored = self._simulate_ble_packet("SmartTV-LivingRoom", -40)
        self.assertIsNone(rec_ignored)

        # 4. Backend searches for Phone 1 via REST API
        resp1 = self.client.post(
            "/api/v1/search",
            data=json.dumps({"device_id": "KINBEACON-PHONE1"}),
            content_type="application/json",
        )
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.get_json()
        self.assertEqual(data1["device_id"], "KINBEACON-PHONE1")
        self.assertEqual(data1["anchor_id"], "TEST-ANCHOR-E2E")
        self.assertEqual(data1["record_count"], 2)
        self.assertEqual(len(data1["records"]), 2)
        self.assertEqual(data1["records"][0]["rssi"], -58)
        self.assertEqual(data1["records"][1]["rssi"], -61)

        # 5. Backend searches for non-existent device
        resp2 = self.client.post(
            "/api/v1/search",
            data=json.dumps({"device_id": "KINBEACON-UNKNOWN"}),
            content_type="application/json",
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.get_json()
        self.assertEqual(data2["record_count"], 0)
        self.assertEqual(data2["records"], [])

        # 6. Insert an expired record (> 15 minutes ago)
        expired_ts = (
            datetime.now(timezone.utc) - timedelta(minutes=20)
        ).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        self.store.insert_signal("KINBEACON-PHONE1", -99, timestamp=expired_ts)

        # Wait briefly for scheduler to purge
        time.sleep(0.25)

        # Verify expired record is purged from both search and database
        resp3 = self.client.post(
            "/api/v1/search",
            data=json.dumps({"device_id": "KINBEACON-PHONE1"}),
            content_type="application/json",
        )
        data3 = resp3.get_json()
        self.assertEqual(data3["record_count"], 2)  # Still 2, the expired one was purged

        # 7. Check status endpoint
        status_resp = self.client.get("/api/v1/status")
        self.assertEqual(status_resp.status_code, 200)
        status_data = status_resp.get_json()
        self.assertEqual(status_data["anchor_id"], "TEST-ANCHOR-E2E")
        self.assertEqual(status_data["unique_devices_seen"], 2)
        self.assertEqual(status_data["db_record_count"], 3)  # 2 for phone1 + 1 for phone2


if __name__ == "__main__":
    unittest.main()
