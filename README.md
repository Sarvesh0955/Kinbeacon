# KinBeacon

KinBeacon is a localized BLE-based search and tracking system designed for venue safety (e.g. child, senior, or asset location in malls, amusement parks, and event spaces).

## Repository Architecture

This repository contains both components of the KinBeacon system:

```
Kinbeacon/
├── Kinbeacon_anchor/          # Anchor Simulation App (runs on distributed laptops/nodes)
└── Kinbeacon_central_server/   # Central Backend Server (orchestration, registry, and zoning)
```

---

### 1. [KinBeacon Central Server](./Kinbeacon_central_server/README.md)
The central backend server built with **FastAPI**, **SQLAlchemy (Async)**, and **httpx**.
- **Zone & Anchor Registry:** Manages zones, anchor network endpoints, physical coordinates, and devices.
- **Concurrent Fan-Out:** Queries all active anchors concurrently with timeouts, 1-retry, and global deadlines.
- **Zone Identification Engine:** Pure algorithm utilizing exponential recency decay, median filtering, multi-factor confidence scoring ($D \times F \times E \times C \times K$), and conflict/velocity sanity checks.
- **Background Jobs:** Fleet health prober (every 15 s) and rolling-window TTL purger (15-min retention).
- **Interactive Docs:** Swagger UI available at `http://localhost:8000/docs`.

See [Kinbeacon_central_server/README.md](./Kinbeacon_central_server/README.md) for full setup instructions and API details.

---

### 2. [KinBeacon Anchor Simulation App](./Kinbeacon_anchor/README.md)
The distributed anchor application running on venue laptops or edge nodes using **Flask** and **Bleak**.
- **Continuous BLE Scanning:** Scans for target device advertisements (`KINBEACON-` prefix).
- **Local SQLite Rolling Window:** Stores timestamped RSSI records and purges signals older than 15 minutes.
- **REST Search API:** Responds to `POST /api/v1/search` with sightings received during the rolling window and reports anchor telemetry on `GET /api/v1/status`.
- **Mock Mode:** Includes a simulated BLE generator (`--mock`) for testing without Bluetooth hardware.

See [Kinbeacon_anchor/README.md](./Kinbeacon_anchor/README.md) for anchor CLI parameters and setup.

---

## Quick Start: End-to-End Local Demo

1. **Start Anchor Simulator:**
   ```bash
   cd Kinbeacon_anchor
   python3 main.py --mock --port 5001 --anchor-id ANCHOR-LAPTOP-01
   ```

2. **Start Central Server:**
   ```bash
   cd Kinbeacon_central_server
   source venv/bin/activate
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. **Seed Venue & Run Device Search:**
   ```bash
   cd Kinbeacon_central_server
   python3 scripts/seed_venue.py --anchor-url http://localhost:5001
   python3 scripts/run_demo.py --device KINBEACON-PHONE1
   ```
