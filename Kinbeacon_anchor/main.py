import argparse
import random
import signal
import sys
import threading
import time

import config
from api.routes import create_app
from ble.demo import DemoRadio
from ble.scanner import start_scanner_thread
from db.store import SignalStore
from scheduler.purge import PurgeScheduler
from utils.logging_config import setup_logger

logger = setup_logger("main")


def start_mock_ble_thread(
    store: SignalStore, stop_event: threading.Event, prefix: str = config.DEVICE_PREFIX
) -> threading.Thread:
    """Simulates incoming BLE advertisements for offline demonstrations."""

    def _mock_worker():
        logger.warning(
            "[MOCK MODE] Simulating incoming BLE advertisements for devices with prefix '%s'...",
            prefix,
        )
        mock_devices = [f"{prefix}phone1", f"{prefix}phone2", f"{prefix}wearable3"]
        while not stop_event.is_set():
            device_id = random.choice(mock_devices)
            rssi = random.randint(-85, -45)
            store.insert_signal(device_id=device_id, rssi=rssi)
            logger.info("[MOCK] Ingested signal: %s (RSSI: %d dBm)", device_id, rssi)
            # Sleep 1.5 - 3.0 seconds between signals
            if stop_event.wait(timeout=random.uniform(1.5, 3.0)):
                break
        logger.info("[MOCK MODE] Simulation worker stopped.")

    thread = threading.Thread(target=_mock_worker, name="MockBLEThread", daemon=True)
    thread.start()
    return thread


def main():
    parser = argparse.ArgumentParser(
        description="KinBeacon Anchor Simulation Server"
    )
    parser.add_argument(
        "--host",
        default=config.API_HOST,
        help=f"API Host to bind (default: {config.API_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.API_PORT,
        help=f"API Port to bind (default: {config.API_PORT})",
    )
    parser.add_argument(
        "--db",
        default=config.DB_PATH,
        help=f"SQLite database path (default: {config.DB_PATH})",
    )
    parser.add_argument(
        "--prefix",
        default=config.DEVICE_PREFIX,
        help=f"BLE advertisement name prefix filter (default: {config.DEVICE_PREFIX})",
    )
    parser.add_argument(
        "--company-id",
        type=lambda x: int(x, 0),
        default=config.COMPANY_ID,
        help=f"Company ID for BLE Manufacturer Data (default: 0x{config.COMPANY_ID:04X} / {config.COMPANY_ID})",
    )
    parser.add_argument(
        "--anchor-id",
        default=config.ANCHOR_ID,
        help=f"Unique anchor identity (default: {config.ANCHOR_ID})",
    )
    parser.add_argument(
        "--retention",
        type=int,
        default=config.RETENTION_MINUTES,
        help=f"Signal retention window in minutes (default: {config.RETENTION_MINUTES})",
    )
    parser.add_argument(
        "--purge-interval",
        type=int,
        default=config.PURGE_INTERVAL_SECONDS,
        help=f"Purge check interval in seconds (default: {config.PURGE_INTERVAL_SECONDS})",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run in mock BLE mode (generates simulated signals for testing without radio)",
    )
    parser.add_argument("--demo-server", help="Venue server URL for the last-mile demo")
    parser.add_argument("--demo-adapter", default="hci0", help="BlueZ adapter for demo TX")
    parser.add_argument("--demo-mock-tx", action="store_true", help="Log demo transmissions without a Linux radio")
    args = parser.parse_args()

    logger.info("==================================================")
    logger.info("Starting KinBeacon Anchor: %s", args.anchor_id)
    logger.info("Database: %s", args.db)
    logger.info("Device Prefix Filter: '%s'", args.prefix or "<ALL>")
    logger.info("Retention Window: %d minutes", args.retention)
    logger.info("Purge Interval: %d seconds", args.purge_interval)
    logger.info("Mock Mode: %s", "ENABLED" if args.mock else "DISABLED (Real BLE)")
    logger.info("==================================================")

    # 1. Initialize Signal Database
    store = SignalStore(db_path=args.db)
    store.init_db()

    # Coordination flag for background workers
    stop_event = threading.Event()

    # 2. Launch Purge Scheduler
    scheduler = PurgeScheduler(
        store=store,
        retention_minutes=args.retention,
        interval_seconds=args.purge_interval,
    )
    scheduler.start()

    demo = None
    demo_thread = None
    if args.demo_server:
        demo = DemoRadio(args.demo_server, args.demo_adapter, args.mock or args.demo_mock_tx)
        demo_thread = demo.start(stop_event)

    # 3. Launch BLE Scanner or Mock Ingestor
    scanner = None
    ble_thread = None
    if args.mock:
        ble_thread = start_mock_ble_thread(
            store=store, stop_event=stop_event, prefix=args.prefix
        )
    else:
        ble_thread, scanner = start_scanner_thread(
            store=store,
            stop_event=stop_event,
            device_prefix=args.prefix,
            company_id=args.company_id,
            demo_receiver=demo.receive if demo else None,
        )

    # 4. Create Flask API App
    app = create_app(store=store, scanner=scanner, anchor_id=args.anchor_id)

    # Graceful Shutdown Handler
    def shutdown_handler(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info("Received signal %s. Initiating graceful shutdown...", sig_name)
        stop_event.set()
        scheduler.stop(timeout=2.0)
        if ble_thread and ble_thread.is_alive():
            ble_thread.join(timeout=3.0)
        if demo_thread:
            demo_thread.join(timeout=3.0)
        store.close()
        logger.info("KinBeacon Anchor shut down successfully.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # 5. Start Flask Server
    logger.info("Starting API server on %s:%d...", args.host, args.port)
    try:
        app.run(host=args.host, port=args.port, threaded=True, debug=False)
    finally:
        stop_event.set()
        scheduler.stop(timeout=2.0)
        store.close()


if __name__ == "__main__":
    main()
