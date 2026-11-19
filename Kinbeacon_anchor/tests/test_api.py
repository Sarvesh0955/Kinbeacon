import json
import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

from api.routes import create_app
from db.store import SignalStore


class DummyScanner:
    def __init__(self, is_running=True):
        self.is_running = is_running


class TestAnchorAPI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_api.db")
        self.store = SignalStore(db_path=self.db_path)
        self.store.init_db()

        self.dummy_scanner = DummyScanner(is_running=True)
        self.app = create_app(
            store=self.store, scanner=self.dummy_scanner, anchor_id="TEST-ANCHOR-01"
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_search_existing_device(self):
        # Insert test records
        self.store.insert_signal("kb-phone1", -58)
        self.store.insert_signal("kb-phone1", -62)
        self.store.insert_signal("kb-other", -75)

        response = self.client.post(
            "/api/v1/search",
            data=json.dumps({"device_id": "kb-phone1"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["device_id"], "kb-phone1")
        self.assertEqual(data["anchor_id"], "TEST-ANCHOR-01")
        self.assertEqual(data["record_count"], 2)
        self.assertEqual(len(data["records"]), 2)
        self.assertEqual(data["records"][0]["rssi"], -58)
        self.assertEqual(data["records"][1]["rssi"], -62)

    def test_search_non_existent_device_returns_empty(self):
        response = self.client.post(
            "/api/v1/search",
            data=json.dumps({"device_id": "kb-notfound"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["device_id"], "kb-notfound")
        self.assertEqual(data["record_count"], 0)
        self.assertEqual(data["records"], [])

    def test_search_missing_device_id_validation(self):
        # Empty body
        resp = self.client.post(
            "/api/v1/search",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.get_json())

        # Empty string
        resp2 = self.client.post(
            "/api/v1/search",
            data=json.dumps({"device_id": "   "}),
            content_type="application/json",
        )
        self.assertEqual(resp2.status_code, 400)

        # Not JSON
        resp3 = self.client.post(
            "/api/v1/search",
            data="not a json",
            content_type="text/plain",
        )
        self.assertEqual(resp3.status_code, 400)

    def test_search_excludes_stale_records(self):
        # Record older than 15 minutes
        stale_ts = (
            datetime.now(timezone.utc) - timedelta(minutes=20)
        ).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        self.store.insert_signal("kb-stale", -80, timestamp=stale_ts)

        response = self.client.post(
            "/api/v1/search",
            data=json.dumps({"device_id": "kb-stale"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["record_count"], 0)
        self.assertEqual(data["records"], [])

    def test_status_endpoint(self):
        self.store.insert_signal("kb-1", -60)
        self.store.insert_signal("kb-2", -70)

        response = self.client.get("/api/v1/status")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["anchor_id"], "TEST-ANCHOR-01")
        self.assertEqual(data["ble_scanner"], "running")
        self.assertEqual(data["db_record_count"], 2)
        self.assertEqual(data["unique_devices_seen"], 2)
        self.assertGreaterEqual(data["uptime_seconds"], 0)

    def test_devices_endpoint(self):
        self.store.insert_signal("kb-dev1", -50)
        self.store.insert_signal("kb-dev1", -52)
        self.store.insert_signal("kb-dev2", -65)

        response = self.client.get("/api/v1/devices")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("devices", data)
        self.assertEqual(len(data["devices"]), 2)


if __name__ == "__main__":
    unittest.main()
