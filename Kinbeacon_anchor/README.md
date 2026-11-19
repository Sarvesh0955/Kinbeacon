# KinBeacon Anchor Simulation App

A lightweight, robust BLE Anchor application running on laptops or edge mini-PCs (macOS/Linux/Windows). It continuously scans for BLE advertisements broadcast by smartphones or wearable beacons, records timestamps and signal strengths (RSSI) into a local rolling-window SQLite database, automatically purges entries older than 15 minutes, and responds to backend search queries via a REST API.

---

## Features

- **Continuous BLE Scanning:** Scans BLE advertisements via [Bleak](https://github.com/hbldh/bleak) on a dedicated asynchronous thread with automatic loop recovery.
- **Manufacturer Specific Data Parsing:** Detects beacons broadcasting via Manufacturer Data (Company ID `0xFFFF` / `65535` default) with robust framing detection:
  - **Compact KV:** `kb-<16-hex-chars>` (19 bytes payload)
  - **Extended Full JSON:** `{"device_id":"kb-<16-hex-chars>"}` (32 bytes payload)
  - **Legacy JSON Base64:** `{"device_id":"kb-<b64>"}` (27 bytes payload)
- **Local Name Fallback:** Falls back to matching the advertised local name or device name against the configured device prefix (`kb-`).
- **Thread-Safe Local Storage:** SQLite with WAL (Write-Ahead Logging) mode and compound indexing (`device_id`, `timestamp`) for sub-millisecond query latency.
- **15-Minute Rolling Window:** Background scheduler periodically purges records older than 15 minutes while queries automatically enforce the cutoff window.
- **REST API Endpoints:** Clean JSON endpoints for device search (`/api/v1/search`), anchor health & stats (`/api/v1/status`), and cataloging seen devices (`/api/v1/devices`).
- **Offline / Mock Mode:** Optional `--mock` CLI flag to simulate BLE signal intake without requiring active Bluetooth hardware or testing in CI environments.

---

## Architecture Overview

```
                      +-------------------------------------------------+
                      |           Smartphones / Wearables               |
                      |               (kimbeacon_app)                   |
                      |  Advertising: Company 0xFFFF / Name "kb-phone1" |
                      +------------------------+------------------------+
                                               | (BLE 2.4 GHz)
                                               v
+-----------------------------------------------------------------------------------------------+
| Laptop / Edge Node Anchor                                                                     |
|                                                                                               |
|   +------------------------------------+                    +-----------------------------+   |
|   |         BLE Scanner Thread         |                    |   Purge Scheduler Thread    |   |
|   |       (Bleak, Asyncio Loop)        |                    |   (Runs every 60 seconds)   |   |
|   | Parses: 0xFFFF (JSON / Compact KV) |                    +--------------+--------------+   |
|   | Fallback: Complete Local Name      |                                   |                  |
|   +------------------+-----------------+                                   |                  |
|                      |                                                     |                  |
|                      | INSERT (device_id, ts, rssi)                        | DELETE < 15 min  |
|                      v                                                     v                  |
|   +---------------------------------------------------------------------------------------+   |
|   |                           SQLite Database (ble_signals.db)                            |   |
|   +------------------------------------------+--------------------------------------------+   |
|                                              ^                                                |
|                                              | SELECT (where device_id = ?                    |
|                                              |         and ts >= now - 15min)                 |
|                               +--------------+--------------+                                 |
|                               |       Flask REST API        |                                 |
|                               |        (Port 8080)          |                                 |
|                               +--------------+--------------+                                 |
+----------------------------------------------|------------------------------------------------+
                                               ^
                                               | HTTP POST /api/v1/search
                                               | { "device_id": "kb-phone1" }
                                               v
                      +-------------------------------------------------+
                      |             Central Backend Server              |
                      +-------------------------------------------------+
```

---

## Installation & Requirements

Python 3.10+ is recommended.

```bash
cd Kinbeacon_anchor
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
*(Binds to `0.0.0.0:8080` by default)*

### 2. Mock Mode (Simulated Signals for Offline Demos)
```bash
python3 main.py --mock --port 5001 --anchor-id ANCHOR-LAPTOP-01
```

### 3. Custom Configuration via CLI
```bash
python3 main.py \
  --anchor-id ANCHOR-LAB-01 \
  --prefix kb- \
  --company-id 0xFFFF \
  --port 8080 \
  --retention 15 \
  --db ble_signals.db
```

### CLI Options

| Argument | Environment Var | Default | Description |
|---|---|---|---|
| `--host` | `API_HOST` | `0.0.0.0` | API bind address |
| `--port` | `API_PORT` | `8080` | API port |
| `--db` | `DB_PATH` | `ble_signals.db` | Path to SQLite database file |
| `--prefix` | `DEVICE_PREFIX` | `kb-` | Filter prefix for BLE advertised names or IDs |
| `--company-id` | `COMPANY_ID` | `65535` (`0xFFFF`)| Company ID for BLE Manufacturer Specific Data |
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
  "device_id": "kb-phone1"
}
```

#### Response (200 OK)
```json
{
  "anchor_id": "ANCHOR-LAPTOP-01",
  "device_id": "kb-phone1",
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
  "device_id": "kb-unknown",
  "record_count": 0,
  "records": []
}
```

#### Example cURL
```bash
curl -X POST http://localhost:8080/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"device_id": "kb-phone1"}'
```

---

### 2. Anchor Health & Metrics
Returns the anchor's operational state, scanner status, and database metrics. Used by the Central Server's health prober.

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
curl http://localhost:8080/api/v1/status
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
      "device_id": "kb-phone1",
      "last_seen": "2026-11-19T00:16:45.789Z",
      "record_count": 89
    },
    {
      "device_id": "kb-phone2",
      "last_seen": "2026-11-19T00:15:20.100Z",
      "record_count": 53
    }
  ]
}
```

---

## Mobile Advertiser Setup (Smartphone / Wearable Side)

The anchor captures BLE advertisements from devices running the **KinBeacon Android App** (`kimbeacon_app`) or custom BLE transmitters. Devices should configure:
1. **Manufacturer Specific Data:** Company ID `0xFFFF` (65535) with payload containing the device ID (e.g. `kb-21a7b9d22bbcb664` or `{"device_id":"kb-phone1"}`).
2. **Advertising Data (Local Name):** Set the Complete Local Name to start with prefix `kb-` (e.g., `kb-phone1`).
3. **Advertising Interval:** Recommended ~100 ms – 500 ms for reliable indoor detection.

---

## Running the Automated Test Suite

Run all unit and end-to-end integration tests using Python's built-in `unittest` runner:

```bash
python3 -m unittest discover tests
```

Expected output:
```
----------------------------------------------------------------------
Ran 22 tests in 0.62s

OK
```
All tests validate:
- SQLite WAL table creation, compound indexing, and signal ingestion
- 15-minute cutoff and background purge scheduling
- Extended Full JSON, Compact KV, and Legacy JSON Base64 payload parsing
- Local name filtering and prefix fallback
- Search, status, and devices REST endpoints
