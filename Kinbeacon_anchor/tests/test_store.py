import os
import tempfile
import threading
import unittest
from datetime import datetime, timezone, timedelta

from db.store import SignalStore, utc_now_iso, cutoff_iso


class TestSignalStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_signals.db")
        self.store = SignalStore(db_path=self.db_path)
        self.store.init_db()

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_init_db_idempotent(self):
        # Calling init_db again should not throw errors
        self.store.init_db()
        stats = self.store.get_stats()
        self.assertEqual(stats["total_records"], 0)
        self.assertEqual(stats["unique_devices"], 0)

    def test_insert_and_query_device(self):
        now_ts = utc_now_iso()
        self.store.insert_signal("KINBEACON-PHONE1", -65, now_ts)
        self.store.insert_signal("KINBEACON-PHONE1", -70)
        self.store.insert_signal("KINBEACON-OTHER", -80)

        # Query PHONE1
        records = self.store.query_device("KINBEACON-PHONE1", since_minutes=15)
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["rssi"], -65)
        self.assertEqual(records[1]["rssi"], -70)

        # Query OTHER
        other_records = self.store.query_device("KINBEACON-OTHER", since_minutes=15)
        self.assertEqual(len(other_records), 1)
        self.assertEqual(other_records[0]["rssi"], -80)

        # Query Non-existent
        empty_records = self.store.query_device("KINBEACON-UNKNOWN", since_minutes=15)
        self.assertEqual(len(empty_records), 0)

    def test_query_device_time_window_filtering(self):
        # Insert a record from 20 minutes ago
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        recent_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        self.store.insert_signal("KINBEACON-PHONE1", -90, timestamp=old_time)
        self.store.insert_signal("KINBEACON-PHONE1", -60, timestamp=recent_time)

        # 15-minute query should only return the recent one
        records = self.store.query_device("KINBEACON-PHONE1", since_minutes=15)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["rssi"], -60)
        self.assertEqual(records[0]["timestamp"], recent_time)

        # 30-minute query should return both
        records_all = self.store.query_device("KINBEACON-PHONE1", since_minutes=30)
        self.assertEqual(len(records_all), 2)

    def test_purge_old_records(self):
        # Insert records with varying ages: 25 mins ago, 16 mins ago, 10 mins ago, 1 min ago
        ts_25m = (datetime.now(timezone.utc) - timedelta(minutes=25)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        ts_16m = (datetime.now(timezone.utc) - timedelta(minutes=16)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        ts_10m = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        ts_1m = (datetime.now(timezone.utc) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        self.store.insert_signal("KINBEACON-1", -70, ts_25m)
        self.store.insert_signal("KINBEACON-1", -72, ts_16m)
        self.store.insert_signal("KINBEACON-1", -65, ts_10m)
        self.store.insert_signal("KINBEACON-2", -55, ts_1m)

        self.assertEqual(self.store.get_stats()["total_records"], 4)

        # Purge records older than 15 minutes (should delete the 25m and 16m records)
        deleted = self.store.purge_old(retention_minutes=15)
        self.assertEqual(deleted, 2)

        stats = self.store.get_stats()
        self.assertEqual(stats["total_records"], 2)

        # Second purge should delete 0 records
        deleted_again = self.store.purge_old(retention_minutes=15)
        self.assertEqual(deleted_again, 0)

    def test_get_devices_and_stats(self):
        self.store.insert_signal("KINBEACON-A", -50)
        self.store.insert_signal("KINBEACON-A", -52)
        self.store.insert_signal("KINBEACON-B", -60)

        stats = self.store.get_stats()
        self.assertEqual(stats["total_records"], 3)
        self.assertEqual(stats["unique_devices"], 2)

        devices = self.store.get_devices()
        self.assertEqual(len(devices), 2)
        device_map = {d["device_id"]: d for d in devices}
        self.assertEqual(device_map["KINBEACON-A"]["record_count"], 2)
        self.assertEqual(device_map["KINBEACON-B"]["record_count"], 1)

    def test_concurrent_writes(self):
        def worker(device_id: str, count: int):
            for i in range(count):
                self.store.insert_signal(device_id, -50 - (i % 20))

        threads = []
        threads_count = 5
        writes_per_thread = 20

        for idx in range(threads_count):
            t = threading.Thread(target=worker, args=(f"KINBEACON-THREAD-{idx}", writes_per_thread))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        stats = self.store.get_stats()
        self.assertEqual(stats["total_records"], threads_count * writes_per_thread)
        self.assertEqual(stats["unique_devices"], threads_count)


if __name__ == "__main__":
    unittest.main()
