import os
import tempfile
import time
import unittest
from datetime import datetime, timezone, timedelta

from db.store import SignalStore
from scheduler.purge import PurgeScheduler


class TestPurgeScheduler(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_scheduler.db")
        self.store = SignalStore(db_path=self.db_path)
        self.store.init_db()

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def test_scheduler_lifecycle(self):
        scheduler = PurgeScheduler(
            store=self.store, retention_minutes=15, interval_seconds=10
        )
        scheduler.start()
        self.assertTrue(scheduler._thread.is_alive())

        # Calling start again should not spawn duplicate threads
        orig_thread = scheduler._thread
        scheduler.start()
        self.assertEqual(scheduler._thread, orig_thread)

        scheduler.stop(timeout=1.0)
        self.assertIsNone(scheduler._thread)

    def test_scheduler_executes_purge(self):
        # Insert 1 old record (20 mins ago) and 1 fresh record (now)
        old_ts = (
            datetime.now(timezone.utc) - timedelta(minutes=20)
        ).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        self.store.insert_signal("KINBEACON-OLD", -80, timestamp=old_ts)
        self.store.insert_signal("KINBEACON-FRESH", -50)

        self.assertEqual(self.store.get_stats()["total_records"], 2)

        # Start scheduler with 0.1s interval for test
        scheduler = PurgeScheduler(
            store=self.store, retention_minutes=15, interval_seconds=0.1
        )
        scheduler.start()

        # Wait briefly for scheduler to fire
        time.sleep(0.3)
        scheduler.stop()

        # Check DB: old record should be deleted, fresh preserved
        stats = self.store.get_stats()
        self.assertEqual(stats["total_records"], 1)
        remaining = self.store.query_device("KINBEACON-FRESH", since_minutes=15)
        self.assertEqual(len(remaining), 1)


if __name__ == "__main__":
    unittest.main()
