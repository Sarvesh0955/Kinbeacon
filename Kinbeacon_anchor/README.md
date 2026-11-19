# KinBeacon Anchor Application (`Kinbeacon_anchor`)

A high-performance, asynchronous Bluetooth Low Energy (BLE) edge listener and local signal cache designed to run continuously on laptops, edge gateways, or mini-PCs (macOS, Linux, and Windows).

The Anchor monitors the 2.4 GHz spectrum for Kinbeacon smartphone/wearable advertisement packets, stores high-resolution signal sightings (RSSI + UTC timestamp) into a rolling-window SQLite database, automatically purges expired records, and exposes a low-latency REST API for the **Kinbeacon Central Server**.

---

## Table of Contents

1. [High-Level System Role](#high-level-system-role)
2. [Key Features](#key-features)
3. [Architecture & Concurrency Model](#architecture--concurrency-model)
4. [BLE Advertisement Ingestion & Framing Formats](#ble-advertisement-ingestion--framing-formats)
   - [Why Company ID 0xFFFF / 65535?](#why-company-id-0xffff--65535)
   - [Supported Framing Encodings](#supported-framing-encodings)
   - [Fallback Detection Strategy](#fallback-detection-strategy)
5. [Local Storage & Rolling Retention](#local-storage--rolling-retention)
6. [REST API Reference](#rest-api-reference)
   - [`POST /api/v1/search`](#1-post-apiv1search)
   - [`GET /api/v1/status`](#2-get-apiv1status)
   - [`GET /api/v1/devices`](#3-get-apiv1devices)
7. [Installation & Prerequisites](#installation--prerequisites)
   - [OS Permissions (macOS / Linux / Windows)](#os-permissions)
8. [Configuration & Environment Variables](#configuration--environment-variables)
9. [Running the Application](#running-the-application)
   - [Production BLE Mode](#1-production-ble-mode)
   - [Mock Mode (Hardware-Free Testing)](#2-mock-mode-hardware-free-testing)
   - [Custom CLI Overrides](#3-custom-cli-overrides)
10. [Diagnostic Utilities](#diagnostic-utilities)
11. [Automated Testing](#automated-testing)
12. [Troubleshooting & Common Issues](#troubleshooting--common-issues)

---

## High-Level System Role

In the Kinbeacon indoor positioning and tracking mesh, **Anchors** serve as the sensory layer:
- **Wearables/Smartphones (`kimbeacon_app`)** broadcast BLE packets containing privacy-preserving Rolling Proximity Identifiers (RPIs) or device tokens.
- **Anchors (`Kinbeacon_anchor`)** pick up these broadcasts, record the observed RSSI, and log sightings into an indexed SQLite store.
- **Central Server (`Kinbeacon_central_server`)** queries distributed anchors concurrently to aggregate RSSI readings and compute device proximity, trilateration, and path history.

```
       [ Android / Wearable (kimbeacon_app) ]
                         |
                         | BLE Advertisements (2.4 GHz)
                         | Company 0xFFFF / Name "kb-..."
                         v
       +------------------------------------+
       |       Kinbeacon Anchor Node        |
       |  (Laptop / Raspberry Pi / Edge PC) |
       +-----------------+------------------+
                         |
                         | HTTP REST API (Port 8080)
                         v
       [ Kinbeacon Central Backend Server ]
```

---

## Key Features

- **Asynchronous BLE Ingestion:** Powered by [Bleak](https://github.com/hbldh/bleak) on an isolated background thread with event-loop auto-recovery.
- **Multi-Format Packet Decoding:** Decodes raw binary payloads, escaped JSON, base64 strings, and compact key-value tokens within BLE Manufacturer Specific Data.
- **Prefix & Identity Filtering:** Filters traffic by configured Company ID and device prefixes (`kb-` by default) to discard surrounding ambient Bluetooth traffic with near-zero overhead.
- **Zero-Latency Concurrency:** Utilizes SQLite in **Write-Ahead Logging (WAL)** mode with compound indexes (`device_id`, `timestamp`), enabling simultaneous reader (API) and writer (BLE scanner) operations without locking conflicts.
- **Automatic 15-Minute Rolling Window:** Background pruning scheduler cleans up entries older than 15 minutes every 60 seconds. API queries strictly filter using real-time cutoff thresholds.
- **Hardware-Free Mocking:** Built-in `--mock` engine simulates multi-device advertisement streams for offline development, Docker builds, and CI pipelines.

---

## Architecture & Concurrency Model

The application coordinates three concurrent worker components connected through a thread-safe SQLite engine:

```
+-----------------------------------------------------------------------------------------------+
| Kinbeacon Anchor Process                                                                      |
|                                                                                               |
|   +------------------------------------+                    +-----------------------------+   |
|   |         BLE Scanner Thread         |                    |   Purge Scheduler Thread    |   |
|   |       (Bleak, Asyncio Loop)        |                    |   (Runs every 60 seconds)   |   |
|   |   Continuous 2.4 GHz radio scans   |                    |   DELETE signals < 15 min   |   |
|   | Parses: 0xFFFF / "kb-" local names |                    +--------------+--------------+   |
|   +------------------+-----------------+                                   |                  |
|                      |                                                     |                  |
|                      | INSERT (device_id, ts, rssi)                        | Prune Old Rows   |
|                      v                                                     v                  |
|   +---------------------------------------------------------------------------------------+   |
|   |                         SQLite Database (WAL Journal Mode)                            |   |
|   |                                  ble_signals.db                                       |   |
|   +------------------------------------------+--------------------------------------------+   |
|                                              ^                                                |
|                                              | SELECT where device_id = ?                     |
|                                              |   and timestamp >= now - 15 min                |
|                               +--------------+--------------+                                 |
|                               |       Flask REST API        |                                 |
|                               |     (Main Process Loop)     |                                 |
|                               +--------------+--------------+                                 |
|                                              ^                                                |
+----------------------------------------------|------------------------------------------------+
                                               |
                                HTTP Requests  | (POST /api/v1/search)
                                               v
                                [ Kinbeacon Central Server ]
```

1. **BLE Scanner Worker (`ble/scanner.py`):** Runs on a dedicated OS thread hosting its own `asyncio` event loop. Captures raw BLE packets, decodes device IDs, and writes directly to the SQLite store.
2. **Purge Scheduler (`scheduler/purge.py`):** A daemon thread executing every `PURGE_INTERVAL_SECONDS` (default: 60s) to keep database size bounded.
3. **REST API Server (`api/routes.py`):** Multi-threaded Flask HTTP server serving endpoints consumed by the Central Server or operator diagnostics.

---

## BLE Advertisement Ingestion & Framing Formats

### Why Company ID `0xFFFF` / `65535`?

* In the Bluetooth SIG specification, **Manufacturer Specific Data** (`AD Type 0xFF`) requires a 2-byte 16-bit Company Identifier (CID).
* `0xFFFF` (`65535` in decimal) is the universal unassigned/experimental company ID widely recognized in the BLE development community for internal prototypes and private mesh networks.
* Using this specific ID allows the anchor's scanner callback to instantly ignore 99%+ of nearby BLE chatter (Apple AirDrop, smart TVs, fitness trackers) at line rate without expensive string allocations.

### Supported Framing Encodings

The anchor automatically detects and unpacks 3 distinct payload encodings transmitted by the mobile application:

| Format Mode | Payload Size | Example Transmitted Payload | Detection Logic |
|---|---|---|---|
| **Compact KV** | **19 Bytes** | `kb-21a7b9d22bbcb664` | Raw UTF-8 string matching regex `kb-[a-zA-Z0-9_\-]+` |
| **Extended Full JSON** | **32 Bytes** | `{"device_id":"kb-1234567890abcdef"}` | Parsed via `json.loads` or regex extraction |
| **Legacy JSON Base64** | **27 Bytes** | `{"device_id":"kb-aGVsYXNka2pm"}` | Base64-wrapped payload inside standard JSON envelope |

### Fallback Detection Strategy

To ensure zero dropped detections during transient connection states or operating-system-level BLE changes, the anchor applies a multi-tier fallback pipeline for every incoming packet:

```
[ Incoming BLE Advertisement ]
               │
               ▼
1. Is configured Company ID (0xFFFF / 65535) present in Manufacturer Data?
     ├── YES ──> Parse payload bytes (JSON or Compact-KV) ──> Extracted ID? ──> [ MATCH ]
     └── NO  ──┐
               ▼
2. Check ANY other Manufacturer Data keys present
     └── Loop all company IDs and attempt payload extraction ──> Extracted ID? ──> [ MATCH ]
               │
               ▼ (None matched)
3. Fallback to Advertised Local Name or Device Name
     └── Does name start with configured prefix (e.g., "kb-")?
           ├── YES ──> [ MATCH ]
           └── NO  ──> [ IGNORE PACKET ]
```

---

## Local Storage & Rolling Retention

Data is persisted locally in `ble_signals.db` with the following schema:

```sql
CREATE TABLE IF NOT EXISTS signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL,  -- ISO-8601 UTC with ms: YYYY-MM-DDTHH:MM:SS.mmmZ
    rssi        INTEGER NOT NULL   -- Signal strength in dBm (e.g., -65)
);

CREATE INDEX IF NOT EXISTS idx_device_time ON signals (device_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_timestamp   ON signals (timestamp);
```

### Concurrency & Retention Guarantees
- **Write-Ahead Logging (WAL):** Enabled via `PRAGMA journal_mode=WAL;` and `PRAGMA synchronous=NORMAL;`. Readers never block writers and writers never block readers.
- **Compound Index (`device_id, timestamp`):** Optimizes bounded range queries `WHERE device_id = ? AND timestamp >= ?` to sub-millisecond execution times.
- **Double-Layered Expiry Enforcement:**
  1. *Lazy Expiry:* The `/api/v1/search` endpoint computes `now - 15 minutes` in memory and applies it to the SQL query clause, guaranteeing queries never return stale data even if the purge thread is delayed.
  2. *Active Expiry:* The `PurgeScheduler` thread physically runs `DELETE FROM signals WHERE timestamp < cutoff` every 60 seconds to reclaim disk space.

---

## REST API Reference

All requests and responses use JSON formatting with standard HTTP status codes.

### 1. `POST /api/v1/search`
Queries the anchor database for all advertisement sightings of a specific target device within the rolling retention window.

- **URL:** `/api/v1/search`
- **Method:** `POST`
- **Headers:** `Content-Type: application/json`

#### Request Payload
```json
{
  "device_id": "kb-phone1"
}
```

#### Response (200 OK — Sighting Found)
```json
{
  "anchor_id": "ANCHOR-LAPTOP-01",
  "device_id": "kb-phone1",
  "record_count": 3,
  "records": [
    {
      "rssi": -58,
      "timestamp": "2026-11-19T07:15:30.123Z"
    },
    {
      "rssi": -62,
      "timestamp": "2026-11-19T07:16:02.456Z"
    },
    {
      "rssi": -59,
      "timestamp": "2026-11-19T07:16:45.789Z"
    }
  ]
}
```

#### Response (200 OK — No Signals in Window)
```json
{
  "anchor_id": "ANCHOR-LAPTOP-01",
  "device_id": "kb-absent-device",
  "record_count": 0,
  "records": []
}
```

#### Error Response (400 Bad Request)
```json
{
  "error": "device_id is required"
}
```

---

### 2. `GET /api/v1/status`
Returns the operational health, BLE radio scanner state, database row counts, and uptime. Used by the Central Server's health prober.

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

---

### 3. `GET /api/v1/devices`
Returns a catalog of all unique devices observed within the active rolling window and their most recent sighting timestamp.

- **URL:** `/api/v1/devices`
- **Method:** `GET`

#### Response (200 OK)
```json
{
  "devices": [
    {
      "device_id": "kb-phone1",
      "last_seen": "2026-11-19T07:16:45.789Z",
      "record_count": 89
    },
    {
      "device_id": "kb-wearable2",
      "last_seen": "2026-11-19T07:15:20.100Z",
      "record_count": 53
    }
  ]
}
```

---

## Installation & Prerequisites

Python **3.10+** is required.

```bash
# Clone and enter directory
cd Kinbeacon_anchor

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### OS Permissions

- **macOS:**
  - macOS requires Bluetooth permissions for the terminal/IDE running Python.
  - On the first scan, an OS prompt will request Bluetooth access. If scanning returns no devices, verify under:
    `System Settings -> Privacy & Security -> Bluetooth` that your terminal application (e.g., Terminal, iTerm2, VSCode) is granted permission.
- **Linux:**
  - Requires BlueZ installed (`sudo apt install bluez bluetooth`).
  - To run without `sudo`, grant raw capabilities to the Python binary:
    ```bash
    sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python3))
    ```
- **Windows:**
  - Requires Windows 10/11 with Bluetooth turned on. Bleak interacts with Windows.Devices.Bluetooth APIs natively.

---

## Configuration & Environment Variables

All parameters can be configured via environment variables or CLI flags (CLI flags take precedence):

| Parameter | Environment Variable | CLI Option | Default | Description |
|---|---|---|---|---|
| Anchor ID | `ANCHOR_ID` | `--anchor-id` | `ANCHOR-LAPTOP-01` | Unique name of this anchor node in the network |
| API Host | `API_HOST` | `--host` | `0.0.0.0` | IP interface to bind the REST API |
| API Port | `API_PORT` | `--port` | `8080` | Port for the REST API |
| Database Path | `DB_PATH` | `--db` | `ble_signals.db` | File path for SQLite storage |
| Device Prefix | `DEVICE_PREFIX` | `--prefix` | `kb-` | String prefix filter for devices |
| Company ID | `COMPANY_ID` | `--company-id` | `65535` (`0xFFFF`) | 16-bit BLE Manufacturer Specific Data CID |
| Retention Window | `RETENTION_MINUTES` | `--retention` | `15` | Sighting age cutoff window (in minutes) |
| Purge Interval | `PURGE_INTERVAL_SECONDS` | `--purge-interval` | `60` | Frequency of background database purge in seconds |
| Debug Mode | `DEBUG` | - | `False` | Enables verbose debug logging |
| Mock Mode | - | `--mock` | `False` | Disables real radio and synthesizes simulated BLE signals |

---

## Running the Application

### 1. Production BLE Mode
Launches the real Bluetooth receiver and Flask API on port 8080:
```bash
python3 main.py
```

### 2. Mock Mode (Hardware-Free Testing)
Simulates randomized incoming BLE packets from `kb-phone1`, `kb-phone2`, and `kb-wearable3` with realistic RSSIs (-85 to -45 dBm). Ideal for UI testing, load testing, or headless environments:
```bash
python3 main.py --mock --port 5001 --anchor-id ANCHOR-SIM-01
```

### 3. Custom CLI Overrides
```bash
python3 main.py \
  --anchor-id ANCHOR-ROOM-302 \
  --port 8081 \
  --company-id 0xFFFF \
  --prefix kb- \
  --retention 30 \
  --purge-interval 120 \
  --db anchors/room302.db
```

---

## Diagnostic Utilities

The repository includes a live BLE inspection utility to verify reception directly in the terminal without running the database or API server:

```bash
python3 scripts/test_ble_live.py
```

This scans and prints full diagnostic packet dumps in real-time when a matching device is discovered:
```text
Listening for BLE packets with Company ID 0xFFFF or 'kb-' prefix...
Press Ctrl+C to stop.

============================================================
🎯 [MATCH] Device Address: 6A:4E:91:2B:10:88
   Local Name    : <None>
   RSSI          : -54 dBm
   Company IDs   : [65535]
   Raw Hex Payload: 6B622D32316137623964323262626362363634
   Raw String    : kb-21a7b9d22bbcb664
   Extracted ID  : kb-21a7b9d22bbcb664 (Mode: Compact-KV)
============================================================
```

---

## Automated Testing

The anchor codebase includes comprehensive test suites covering database atomicity, background purge timers, multi-framing payload parsers, API endpoints, and end-to-end integration flows.

Run the test suite using Python's built-in test runner:
```bash
python3 -m unittest discover tests -v
```

### Tested Components
- `tests/test_store.py`: Validates SQLite initialization, WAL mode verification, concurrent insertions, and cutoff queries.
- `tests/test_scanner.py`: Validates decoding of Compact KV, Extended Full JSON, Legacy Base64 frames, and device name fallbacks.
- `tests/test_scheduler.py`: Tests the background purge lifecycle, verifying that rows older than the retention threshold are cleanly removed.
- `tests/test_api.py`: Validates all Flask routes (`/search`, `/status`, `/devices`), including invalid JSON schemas and missing parameters.
- `tests/test_integration.py`: End-to-end verification linking simulated scanner inserts to live API queries.

---

## Troubleshooting & Common Issues

### 1. `bleak.exc.BleakDBusError: org.freedesktop.DBus.Error.AccessDenied` (Linux)
* **Cause:** User account lacks permissions to access BlueZ DBus adapters.
* **Fix:** Add your user to the `bluetooth` group or set raw capabilities on Python:
  ```bash
  sudo usermod -aG bluetooth $USER
  sudo setcap 'cap_net_raw,cap_net_admin+eip' $(readlink -f $(which python3))
  ```

### 2. Scanner starts but detects 0 devices (macOS)
* **Cause:** macOS TCC security subsystem blocked Bluetooth access for Terminal/Python.
* **Fix:** Open **System Settings -> Privacy & Security -> Bluetooth**, toggle terminal off and on, and restart terminal.

### 3. Database is locked (`sqlite3.OperationalError: database is locked`)
* **Cause:** Multiple external tools accessing SQLite concurrently without WAL mode enabled.
* **Fix:** The app automatically enables `PRAGMA journal_mode=WAL;`. Avoid opening the SQLite file with external GUI tools in exclusive lock mode while the anchor is running.
