# KinBeacon Operator Dashboard

A modern, real-time web dashboard for configuring, orchestrating, and demonstrating the **KinBeacon** BLE indoor localization and safety system. Built with **React 18**, **TypeScript**, **Vite**, and **Tailwind CSS**.

---

## Features

- **System Overview:**
  - Real-time counters for registered zones, anchors, wearables, and total search requests executed.
  - Live anchor fleet breakdown (UP / DEGRADED / DOWN / UNKNOWN).
  - 1-Click **"Seed Venue"** button that initializes a complete multi-zone venue with anchors and test devices.
- **Zone Management:**
  - View all venue zones, centroid coordinates $(x, y)$, and dimensional metadata.
  - Create and edit zones.
  - Configure zone adjacency topologies to drive conflict detection and search-area expansion.
- **Anchor Fleet Management:**
  - Register, edit, and delete Bluetooth LE anchors with LAN, local, or tunnel endpoints (e.g., DevTunnels, ngrok).
  - Assign physical coordinates $(x, y, \text{floor})$ and parent zones.
  - **Inline Auto-Verification:** Test anchor connectivity and query `/api/v1/status` directly from the UI.
  - Real-time circuit breaker status and failure tracking.
- **Wearable Device Registry:**
  - Register and manage wearable beacons and wristbands.
  - Active/Inactive status toggle with soft-delete capabilities.
  - Quick-action **"Locate"** button that jumps straight to device search.
- **Device Location Detection & Diagnostics:**
  - Execute live concurrent search fan-outs across all active anchors.
  - Real-time localized result display:
    - **Winning Zone** resolution
    - **Estimated Coordinates** $(x, y, \text{floor})$
    - **Algorithm Flags:** `STALE`, `CONFLICT`, `SINGLE_ANCHOR`, `PARTIAL_COVERAGE`, `NOT_SEEN`
    - **Ranked Candidate Zones Table:** Candidate zones sorted by relative probability
    - **Signal Evidence Table:** Per-anchor sample count, smoothed RSSI (dBm), calculated anchor score, and sighting age
    - **Fleet Fan-out Summary:** Counts of targeted, responded, timed-out, and failed anchors
- **Fleet Connectivity & Health:**
  - Live telemetry dashboard polling anchor states every 15 seconds.
  - Monitors uptime, scanner state, database records count, and network latency.
- **Search Request History:**
  - Historical log of all past search requests with UUIDs, timestamps, latencies, and estimated zones.

---

## Architecture & Technology Stack

- **Framework:** React 18 with TypeScript
- **Bundler & Dev Server:** Vite 5
- **Styling:** Tailwind CSS with Lucide React icons
- **State & Data Fetching:** Axios with automated Vite reverse-proxy configuration
- **Notifications:** React Hot Toast

### Reverse Proxy Configuration
In development mode, Vite automatically proxies API requests from `http://localhost:3000` to the KinBeacon Central Server at `http://localhost:8000`:
- `/api/*` $\to$ `http://localhost:8000/api/*`
- `/health` $\to$ `http://localhost:8000/health`

---

## Getting Started

### 1. Prerequisites
- Node.js 18+ (tested on Node 20 & 24)
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

The dashboard will open on [http://localhost:3000](http://localhost:3000).

### 4. Production Build

```bash
npm run build
npm run preview
```

---

## End-to-End Simulation Demo

You can run a full localization demo using all KinBeacon components on a single machine:

1. **Start Anchor Simulator (Terminal 1):**
   ```bash
   cd Kinbeacon_anchor
   python3 main.py --mock --port 5001 --anchor-id ANCHOR-LAPTOP-01
   ```

2. **Start Central Server (Terminal 2):**
   ```bash
   cd Kinbeacon_central_server
   source venv/bin/activate
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

3. **Start Dashboard (Terminal 3):**
   ```bash
   cd Kinbeacon_dashboard
   npm run dev
   ```

4. **Run the Workflow:**
   - Open [http://localhost:3000](http://localhost:3000).
   - On the **Overview** page, click the **"Seed Venue"** button to populate demo zones and anchors.
   - Go to **"Devices"**, locate `kb-phone1`, and click the **"Locate"** button (or navigate to **"Device Search"** and search for `kb-phone1`).
   - Observe the live confidence score, signal evidence table, and estimated coordinates!
