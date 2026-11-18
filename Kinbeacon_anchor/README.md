# KinBeacon Anchor Simulation App

A lightweight, robust BLE Anchor simulation running on a laptop (macOS/Linux/Windows). It continuously scans for BLE advertisements broadcast by smartphones or wearable beacons, records timestamps and signal strengths (RSSI) into a local rolling-window SQLite database, automatically purges entries older than 15 minutes, and responds to backend search queries via a REST API.

---

## Features

- **Continuous Real BLE Scanning:** Scans actual BLE advertisements via [Bleak](https://github.com/hbldh/bleak) on a dedicated asynchronous thread.
- **Prefix-Based Filtering:** Focuses specifically on target devices (e.g., prefix `KINBEACON-`), avoiding noise from incidental Bluetooth peripherals.
- **Thread-Safe Local Storage:** SQLite with WAL (Write-Ahead Logging) mode and compound indexing (`device_id`, `timestamp`) for high concurrency and sub-millisecond query latency.
- **15-Minute Rolling Window:** Background scheduler periodically purges records older than 15 minutes while queries automatically enforce the cutoff window.
- **REST API Endpoints:** Clean JSON endpoints for device search (`/api/v1/search`), anchor health & stats (`/api/v1/status`), and cataloging seen devices (`/api/v1/devices`).
- **Offline / Mock Mode:** Optional `--mock` CLI flag to simulate BLE signal intake without requiring active Bluetooth hardware or testing in CI environments.

---

## Architecture Overview

```
                      +-----------------------------------+
                      |   Smartphones (Custom BLE Apps)   |
                      |   Advertising: "KINBEACON-PHONE1" |
                      +-----------------+-----------------+
                                        | (BLE 2.4 GHz)
                                        v
+--------------------------------------------------------------------------------+
| Laptop Anchor                                                                  |
|                                                                                |
|   +--------------------------+                 +---------------------------+   |
|   |   BLE Scanner Thread     |                 |   Purge Scheduler Thread  |   |
|   |   (Bleak, Asyncio Loop)  |                 |   (Runs every 60 seconds) |   |
|   +------------+-------------+                 +-------------+-------------+   |
|                |                                             |                 |
|                | INSERT (device_id, ts, rssi)                | DELETE < 15 min |
|                v                                             v                 |
|   +------------------------------------------------------------------------+   |
|   |                     SQLite Database (ble_signals.db)                   |   |
|   +------------------------------------+-----------------------------------+   |
|                                        ^                                       |
|                                        | SELECT (where device_id = ?           |
|                                        |         and ts >= now - 15min)        |
|                         +--------------+--------------+                        |
|                         |      Flask REST API         |                        |
|                         |       (Main Thread)         |                        |
|                         +--------------+--------------+                        |
+----------------------------------------|---------------------------------------+
                                         ^
                                         | HTTP POST /api/v1/search
                                         | { "device_id": "KINBEACON-PHONE1" }
                                         v
                      +-----------------------------------+
                      |          Backend Server           |
                      +-----------------------------------+
```

---

## Installation & Requirements

Python 3.10+ is recommended.

```bash
pip install -r requirements.txt
```

### Dependencies
- `bleak` (>= 3.1.0)
- `Flask` (>= 3.0.0)

*(Note: On macOS, Bluetooth permission will be prompted by the system on first run. Please allow terminal/Python access).*

---

## Running the Anchor

### 1. Normal Mode (Real BLE Radio Scanning)
```bash
python3 main.py
```

### 2. Mock Mode (Simulated Signals for Offline Demos)
```bash
python3 main.py --mock
```

### 3. Custom Configuration via CLI
```bash
python3 main.py \
  --anchor-id ANCHOR-LAB-01 \
  --prefix KINBEACON- \
  --port 5000 \
  --retention 15 \
  --db ble_signals.db
```

### CLI Options

| Argument | Environment Var | Default | Description |
|---|---|---|---|
| `--host` | `API_HOST` | `0.0.0.0` | API bind address |
| `--port` | `API_PORT` | `5000` | API port |
| `--db` | `DB_PATH` | `ble_signals.db` | Path to SQLite database file |
| `--prefix` | `DEVICE_PREFIX` | `KINBEACON-` | Filter prefix for BLE advertised names |
| `--anchor-id` | `ANCHOR_ID` | `ANCHOR-LAPTOP-01` | Unique anchor identity identifier |
| `--retention` | `RETENTION_MINUTES` | `15` | Rolling window retention in minutes |
| `--purge-interval` | `PURGE_INTERVAL_SECONDS`| `60` | Periodic database purge check interval |
| `--mock` | - | `False` | Run mock signal generator for offline testing |

---

## API Documentation

### 1. Device Search
Returns all signal records received for a specific device within the rolling 15-minute window.

- **URL:** `/api/v1/search`
- **Method:** `POST`
- **Headers:** `Content-Type: application/json`

#### Request Body
```json
{
  "device_id": "KINBEACON-PHONE1"
}
```

#### Response (200 OK)
```json
{
  "anchor_id": "ANCHOR-LAPTOP-01",
  "device_id": "KINBEACON-PHONE1",
  "record_count": 3,
  "records": [
    {
      "rssi": -58,
      "timestamp": "2026-11-19T00:15:30.123Z"
    },
    {
      "rssi": -62,
      "timestamp": "2026-11-19T00:16:02.456Z"
    },
    {
      "rssi": -59,
      "timestamp": "2026-11-19T00:16:45.789Z"
    }
  ]
}
```

#### Empty Result (Device Not Detected in Last 15 Min)
```json
{
  "anchor_id": "ANCHOR-LAPTOP-01",
  "device_id": "KINBEACON-UNKNOWN",
  "record_count": 0,
  "records": []
}
```

#### Example cURL
```bash
curl -X POST http://localhost:5000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"device_id": "KINBEACON-PHONE1"}'
```

---

### 2. Anchor Health & Metrics
Returns the anchor's operational state, scanner status, and database metrics.

- **URL:** `/api/v1/status`
- **Method:** `GET`

#### Response (200 OK)
```json
{
  "anchor_id": "ANCHOR-LAPTOP-01",
  "ble_scanner": "running",
  "db_record_count": 142,
  "unique_devices_seen": 3,
  "uptime_seconds": 640
}
```

#### Example cURL
```bash
curl http://localhost:5000/api/v1/status
```

---

### 3. List Seen Devices
Lists all devices currently tracked in the database along with their last seen timestamp.

- **URL:** `/api/v1/devices`
- **Method:** `GET`

#### Response (200 OK)
```json
{
  "devices": [
    {
      "device_id": "KINBEACON-PHONE1",
      "last_seen": "2026-11-19T00:16:45.789Z",
      "record_count": 89
    },
    {
      "device_id": "KINBEACON-PHONE2",
      "last_seen": "2026-11-19T00:15:20.100Z",
      "record_count": 53
    }
  ]
}
```

---

## Mobile Advertiser Setup (Smartphone Side)

The anchor requires smartphones to broadcast BLE advertisements. Your custom mobile app should configure:
1. **Advertising Data (Local Name):** Set the Complete Local Name to start with the configured prefix, e.g. `KINBEACON-PHONE1` or `KINBEACON-USER42`.
2. **Advertising Mode:** Non-connectable or connectable undirected advertising.
3. **Interval:** Recommended ~100 ms – 500 ms for reliable indoor detection.

---

## Running the Automated Test Suite

Run all unit and end-to-end integration tests using Python's built-in `unittest` runner:

```bash
python3 -m unittest discover tests
```

Expected output:
```
----------------------------------------------------------------------
Ran 20 tests in 0.65s

OK
```
