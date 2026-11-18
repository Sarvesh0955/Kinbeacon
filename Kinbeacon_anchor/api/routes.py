import time
from flask import Blueprint, request, jsonify, current_app, Flask

import config
from db.store import SignalStore
from utils.logging_config import setup_logger

logger = setup_logger("api.routes")

api_bp = Blueprint("api_v1", __name__)


@api_bp.route("/search", methods=["POST"])
def search_device():
    """
    Query anchor database for recent advertisement logs of a specific device_id.
    Rolling window is defined by config.RETENTION_MINUTES (default 15 minutes).
    """
    if not request.is_json:
        return jsonify({"error": "Request body must be JSON"}), 400

    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict) or "device_id" not in data:
        return jsonify({"error": "device_id is required"}), 400

    device_id = str(data["device_id"]).strip()
    if not device_id:
        return jsonify({"error": "device_id cannot be empty"}), 400

    store: SignalStore = current_app.config["STORE"]
    anchor_id: str = current_app.config.get("ANCHOR_ID", config.ANCHOR_ID)

    try:
        records = store.query_device(
            device_id=device_id, since_minutes=config.RETENTION_MINUTES
        )
        logger.info(
            "Search request for '%s': found %d records (last %d min)",
            device_id,
            len(records),
            config.RETENTION_MINUTES,
        )
        return (
            jsonify(
                {
                    "device_id": device_id,
                    "anchor_id": anchor_id,
                    "record_count": len(records),
                    "records": records,
                }
            ),
            200,
        )
    except Exception as exc:
        logger.error("Error executing search query for '%s': %s", device_id, exc)
        return jsonify({"error": "Internal database error"}), 500


@api_bp.route("/status", methods=["GET"])
def anchor_status():
    """
    Returns anchor system health, BLE scanner status, and database metrics.
    """
    store: SignalStore = current_app.config["STORE"]
    scanner = current_app.config.get("SCANNER")
    anchor_id: str = current_app.config.get("ANCHOR_ID", config.ANCHOR_ID)
    start_time: float = current_app.config.get("START_TIME", time.time())

    stats = store.get_stats()
    scanner_status = "running" if (scanner and scanner.is_running) else "idle"

    return (
        jsonify(
            {
                "anchor_id": anchor_id,
                "ble_scanner": scanner_status,
                "db_record_count": stats["total_records"],
                "unique_devices_seen": stats["unique_devices"],
                "uptime_seconds": int(time.time() - start_time),
            }
        ),
        200,
    )


@api_bp.route("/devices", methods=["GET"])
def list_devices():
    """
    Returns list of all devices ever recorded in the current database window.
    """
    store: SignalStore = current_app.config["STORE"]
    devices = store.get_devices()
    return jsonify({"devices": devices}), 200


def create_app(
    store: SignalStore, scanner=None, anchor_id: str = config.ANCHOR_ID
) -> Flask:
    """Application factory for the Anchor REST API."""
    app = Flask(__name__)
    app.config["STORE"] = store
    app.config["SCANNER"] = scanner
    app.config["ANCHOR_ID"] = anchor_id
    app.config["START_TIME"] = time.time()

    app.register_blueprint(api_bp, url_prefix="/api/v1")
    return app
