import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from utils.logging_config import setup_logger

logger = setup_logger("db.store")


def utc_now_iso() -> str:
    """Returns current UTC time in ISO-8601 format with millisecond precision and Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def cutoff_iso(minutes_ago: int) -> str:
    """Returns ISO-8601 UTC timestamp corresponding to N minutes in the past."""
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class SignalStore:
    """Thread-safe SQLite storage for BLE advertisement signals."""

    def __init__(self, db_path: str = "ble_signals.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._connect()

    def _connect(self) -> None:
        """Establishes SQLite connection with WAL journal mode."""
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            # Enable WAL mode for high concurrency between reader/writer threads
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")

    def init_db(self) -> None:
        """Initializes tables and indexes if they do not exist."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id   TEXT    NOT NULL,
                    timestamp   TEXT    NOT NULL,
                    rssi        INTEGER NOT NULL
                );
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_device_time
                ON signals (device_id, timestamp);
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON signals (timestamp);
                """
            )
            self._conn.commit()
            logger.info("Database initialized successfully at '%s'", self.db_path)

    def insert_signal(self, device_id: str, rssi: int, timestamp: Optional[str] = None) -> int:
        """
        Inserts a single signal reading into the database.
        Returns the inserted record ID.
        """
        ts = timestamp or utc_now_iso()
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                "INSERT INTO signals (device_id, timestamp, rssi) VALUES (?, ?, ?);",
                (device_id, ts, rssi),
            )
            self._conn.commit()
            return cursor.lastrowid

    def query_device(self, device_id: str, since_minutes: int = 15) -> List[Dict[str, Any]]:
        """
        Queries all records for a specific device within the last `since_minutes` window.
        Returns ordered list of dicts with 'timestamp' and 'rssi'.
        """
        since_ts = cutoff_iso(since_minutes)
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                SELECT timestamp, rssi
                FROM signals
                WHERE device_id = ? AND timestamp >= ?
                ORDER BY timestamp ASC;
                """,
                (device_id, since_ts),
            )
            rows = cursor.fetchall()
            return [{"timestamp": row["timestamp"], "rssi": row["rssi"]} for row in rows]

    def purge_old(self, retention_minutes: int = 15) -> int:
        """
        Deletes all records older than `retention_minutes`.
        Returns number of deleted rows.
        """
        cutoff_ts = cutoff_iso(retention_minutes)
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("DELETE FROM signals WHERE timestamp < ?;", (cutoff_ts,))
            deleted_count = cursor.rowcount
            self._conn.commit()
            if deleted_count > 0:
                logger.info(
                    "Purged %d records older than %d minutes (cutoff: %s)",
                    deleted_count,
                    retention_minutes,
                    cutoff_ts,
                )
            return deleted_count

    def get_stats(self) -> Dict[str, Any]:
        """Returns summary statistics for the database."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total_count FROM signals;")
            total_count = cursor.fetchone()["total_count"]

            cursor.execute("SELECT COUNT(DISTINCT device_id) AS unique_devices FROM signals;")
            unique_devices = cursor.fetchone()["unique_devices"]

            cursor.execute("SELECT MIN(timestamp) AS earliest, MAX(timestamp) AS latest FROM signals;")
            row = cursor.fetchone()
            earliest = row["earliest"]
            latest = row["latest"]

            return {
                "total_records": total_count,
                "unique_devices": unique_devices,
                "earliest_record": earliest,
                "latest_record": latest,
            }

    def get_devices(self) -> List[Dict[str, Any]]:
        """Returns a list of all devices seen, with last seen timestamp and total record count."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                SELECT device_id, MAX(timestamp) AS last_seen, COUNT(*) AS record_count
                FROM signals
                GROUP BY device_id
                ORDER BY last_seen DESC;
                """
            )
            rows = cursor.fetchall()
            return [
                {
                    "device_id": row["device_id"],
                    "last_seen": row["last_seen"],
                    "record_count": row["record_count"],
                }
                for row in rows
            ]

    def close(self) -> None:
        """Closes database connection cleanly."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
                logger.info("Database connection closed")
