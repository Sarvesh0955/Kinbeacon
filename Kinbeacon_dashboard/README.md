# KinBeacon Central Server Dashboard

A minimal, real-time web dashboard for orchestrating and demonstrating the **KinBeacon** BLE indoor localization and safety system.

## Features

- **System Overview:** Real-time counters for zones, anchors, wearables, and live anchor fleet state (UP / DEGRADED / DOWN / UNKNOWN). Includes a 1-click **Seed Venue** button.
- **Zone Management:** Create venue zones, set coordinates & centroids, configure zone adjacency graphs for conflict detection and search-area expansion.
- **Anchor Management:** Register, update, and monitor Bluetooth LE anchors; inline auto-verification against anchor HTTP endpoints (`/api/v1/status`); failure tracking and circuit breaker visibility.
- **Wearable Device Registry:** Register and manage BLE beacons/wristbands with status badges and quick-action location searches.
- **Device Location Detection:** Query the distributed anchor fleet concurrently, aggregate Bluetooth RSSI logs, and display:
  - Winning zone & confidence score (with `HIGH`, `MEDIUM`, `LOW` indicator)
  - Estimated physical coordinates $(x, y, \text{floor})$
  - Algorithm flags (`STALE`, `CONFLICT`, `SINGLE_ANCHOR`, `PARTIAL_COVERAGE`, `NOT_SEEN`)
  - Ranked candidate zones table
  - Signal evidence table (per-anchor samples, smoothed RSSI, score, age)
  - Fleet fan-out summary (targeted, responded, timed out, failed, unreachable)
- **Search Request History:** Audit past search requests, timestamps, and zone estimates.
- **Fleet Connectivity & Health:** Live telemetry and 15-second background polling of anchors, heartbeat state, and circuit-breaker tripping.

---

## Getting Started

### 1. Prerequisites
- Node.js 18+ (tested on Node v24)
- Running KinBeacon Central Server on `http://localhost:8000`

### 2. Setup & Installation

```bash
cd Kinbeacon_dashboard
npm install
```

### 3. Development Server

```bash
npm run dev
```

The dashboard will open on [http://localhost:3000](http://localhost:3000). All API calls (`/api/...` and `/health`) are automatically proxied to the central server on `http://localhost:8000`.

### 4. Production Build

```bash
npm run build
npm run preview
```

---

## End-to-End Simulation Demo

1. **Start Anchor Simulator (Terminal 1):**
   ```bash
   cd Kinbeacon_anchor
   python3 main.py --mock --port 5001 --anchor-id ANCHOR-LAPTOP-01
   ```

2. **Start Central Server (Terminal 2):**
   ```bash
   cd Kinbeacon_central_server
   ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

3. **Start Dashboard (Terminal 3):**
   ```bash
   cd Kinbeacon_dashboard
   npm run dev
   ```

4. Open [http://localhost:3000](http://localhost:3000).
5. Click **"Seed Venue"** on the Overview page (or register zones and anchors manually).
6. Click **"Locate Device"** or navigate to **Device Search** and enter `KINBEACON-PHONE1` to execute the full localization workflow!
