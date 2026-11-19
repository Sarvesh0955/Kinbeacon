# KinBeacon

**KinBeacon** is a localized Bluetooth Low Energy (BLE) search and tracking system designed for venue safety (e.g., child, senior, or high-value asset location in malls, amusement parks, schools, and event spaces).

The system continuously captures BLE advertisement signals across a distributed fleet of anchor nodes, aggregates sightings in real time via a central server, and executes a pure mathematical zone estimation engine to compute high-accuracy localization with multi-factor confidence scoring.

---

## System Architecture

KinBeacon is architected as four integrated components:

```
                                  +-----------------------------------------+
                                  |         Android Wearable Beacon         |
                                  |             (kimbeacon_app)             |
                                  |   Broadcasts BLE RPI (Company 0xFFFF)   |
                                  +--------------------+--------------------+
                                                       |
                                                       | BLE Advertisements (2.4 GHz)
                                                       v
                       +---------------------------------------------------------------+
                       |                Distributed Anchor Fleet Nodes                 |
                       |                      (Kinbeacon_anchor)                       |
                       |       Laptops / Edge nodes running Bleak + Flask + SQLite     |
                       |           Anchor 1 (:8080)   Anchor 2 (:5001)   ...           |
                       +-------------------------------+-------------------------------+
                                                       ^
                                                       | HTTP Pull (/api/v1/search)
                                                       | Concurrent Async Fan-Out
                                                       v
                       +---------------------------------------------------------------+
                       |                    Central Backend Server                     |
                       |                  (Kinbeacon_central_server)                   |
                       |        FastAPI + SQLAlchemy Async + Pure Zoning Engine        |
                       |       Coordinates, Confidence Scoring, Fleet Health Prober    |
                       +-------------------------------+-------------------------------+
                                                       ^
                                                       | REST API & Health Probing
                                                       | (Vite Proxy :3000 -> :8000)
                                                       v
                       +---------------------------------------------------------------+
                       |                   Operator Web Dashboard                      |
                       |                    (Kinbeacon_dashboard)                      |
                       |            React 18 + Vite + Tailwind CSS + Lucide            |
                       |         Venue Seeding, Live Search, Fleet Diagnostics         |
                       +---------------------------------------------------------------+
```

---

## Repository Components

```
Kinbeacon/
├── Kinbeacon_central_server/   # Central Backend Server (FastAPI, async fan-out, pure zoning engine)
├── Kinbeacon_anchor/           # Anchor Node App (Flask, Bleak BLE scanner, SQLite rolling window)
├── Kinbeacon_dashboard/        # Operator Web Dashboard (React 18, Vite, Tailwind CSS, real-time UI)
└── kimbeacon_app/              # Wearable / Smartphone Advertiser App (Android, Kotlin, Jetpack Compose)
```

### 1. [KinBeacon Central Server](./Kinbeacon_central_server/README.md)
The central backend server built with **FastAPI**, **SQLAlchemy (Async)**, and **httpx**.
- **Zone & Anchor Registry:** Manages zones, physical $(x, y, \text{floor})$ coordinates, anchor network endpoints (LAN / DevTunnels / ngrok), and tracked devices.
- **Concurrent Fan-Out:** Queries all active anchors concurrently with bounded concurrency, 1-retry, circuit breaker protection, and a 5-second global deadline.
- **Zone Identification Engine:** Pure side-effect-free algorithm utilizing exponential recency decay ($\tau=20\,\text{s}$), median filtering, and multi-factor confidence scoring:
  $$\text{Confidence} = D \times F \times E \times C \times K$$
  *(Dominance $\times$ Freshness $\times$ Evidence $\times$ Coverage $\times$ Conflict)*
- **Background Jobs:** Fleet health prober (every 15 s) and rolling-window TTL purger (15-min retention).
- **Interactive Documentation:** Swagger UI at `http://localhost:8000/docs`.

### 2. [KinBeacon Anchor Simulation App](./Kinbeacon_anchor/README.md)
The edge anchor node application running on venue laptops or edge mini-PCs using **Flask**, **Bleak**, and **SQLite**.
- **Continuous BLE Scanning:** Scans for BLE advertisements using custom Manufacturer Specific Data (Company ID `0xFFFF` / `65535`) or local name prefix (`kb-`).
- **Framing Support:** Handles Compact KV (`kb-<hex>`), Extended Full JSON (`{"device_id":"kb-<hex>"}`), and Legacy JSON Base64 payloads.
- **15-Minute Rolling Window:** Stores timestamped RSSI records in a thread-safe SQLite WAL database and automatically purges records older than 15 minutes.
- **REST Search API:** Responds to `POST /api/v1/search` with sightings and reports anchor telemetry via `GET /api/v1/status`.
- **Mock Mode:** Includes a simulated BLE generator (`--mock`) for testing without Bluetooth radio hardware.

### 3. [KinBeacon Operator Dashboard](./Kinbeacon_dashboard/README.md)
A responsive web application built with **React 18**, **TypeScript**, **Vite**, and **Tailwind CSS**.
- **1-Click Venue Seeding:** Automatically provisions demo zones, anchors, and test devices with one click.
- **Real-Time Localization:** Live device lookup rendering candidate zones, winning zone, confidence rating, estimated coordinates, algorithm flags (`STALE`, `CONFLICT`, `SINGLE_ANCHOR`, etc.), and anchor evidence table.
- **Fleet Health Monitor:** Live telemetry, heartbeat tracking, and circuit-breaker diagnostics for all registered anchors.
- **Zone & Anchor Management:** Visual forms for configuring zones, centroids, adjacency graphs, and anchor verification.

### 4. [KinBeacon Mobile / Wearable App](./kimbeacon_app/README.md)
A native Android application built with **Kotlin** and **Jetpack Compose** that turns any smartphone or wearable into a KinBeacon beacon.
- **Foreground BLE Advertising:** Uses `KinBeaconAdvertiserService` with partial wake lock for non-stop advertisement broadcasting.
- **Multiple Framing Modes:** Supports Compact KV, Extended Full JSON, and Legacy JSON Base64 packet framing with Company ID `0xFFFF`.
- **Rotating Proximity Identifiers (RPI):** Cryptographic key generation and ephemeral ID rotation for privacy.
- **Real-Time Diagnostic UI:** On-screen inspection of active device ID, raw PDU hex bytes, packet transmission counter, and execution latency ($\mu\text{s}$).

---

## Last-Mile Find Demo

Run the two-phone LAN rehearsal or the live BLE search with the optional tablet relay. See the [setup and rehearsal guide](./LAST_MILE_DEMO.md).

## Quick Start: End-to-End Local Demo

Run a complete demonstration locally on a single machine:

### 1. Start the Anchor Node (Simulator / Mock Mode)
```bash
cd Kinbeacon_anchor
python3 main.py --mock --port 5001 --anchor-id ANCHOR-LAPTOP-01
```
*(Anchor REST API will run at `http://localhost:5001`)*

### 2. Start the Central Backend Server
```bash
cd Kinbeacon_central_server
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*(FastAPI server will run at `http://localhost:8000`, docs at `http://localhost:8000/docs`)*

### 3. Start the Operator Dashboard
```bash
cd Kinbeacon_dashboard
npm install
npm run dev
```
*(Dashboard opens at `http://localhost:3000` with automated proxy to the central server)*

### 4. Seed Venue & Run a Device Search

**Option A — Via Dashboard (Recommended):**
1. Open [http://localhost:3000](http://localhost:3000).
2. Click the **"Seed Venue"** button on the Overview page.
3. Navigate to **"Device Search"** and locate device `kb-phone1` (or click **"Locate Device"** directly from the Wearables table).

**Option B — Via CLI Scripts:**
```bash
cd Kinbeacon_central_server
./venv/bin/python scripts/seed_venue.py --anchor-url http://localhost:5001
./venv/bin/python scripts/run_demo.py --device kb-phone1
```

---

## Automated Test Suites

All subprojects include automated test coverage:

- **Anchor Tests:**
  ```bash
  cd Kinbeacon_anchor
  python3 -m unittest discover tests
  ```
  *(22 unit and integration tests covering SQLite WAL storage, purge scheduler, and BLE packet parsers)*

- **Central Server Tests:**
  ```bash
  cd Kinbeacon_central_server
  ./venv/bin/pytest -v
  ```
  *(17 automated tests covering zoning engine, conflict detection, concurrent transport, and API routes)*

---

## License

This project is licensed under the Apache 2.0 / MIT License.
