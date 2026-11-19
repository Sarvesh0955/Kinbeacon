# KinBeacon Central Server

The central orchestration server for the **KinBeacon** indoor localization and safety system. It manages the venue registry (zones, anchors, and registered wearable devices), initiates search fan-outs across distributed Bluetooth anchors, aggregates and filters signal sightings, and calculates accurate zone estimates with confidence scoring.

---

## Architecture Overview

```
 [Anchor Laptop 1 :5000] ──┐
 [Anchor Laptop 2 :5000] ──┼── Private Venue LAN ──── [Central Server :8000]
 [Anchor Laptop N :500x] ──┘                                 │
                                                  Guardian App / Staff Dashboard
```

- **Communication Direction:** Pull-based. The central server initiates HTTP calls to each anchor's configured `base_url` (`POST /api/v1/search` and `GET /api/v1/status`). Anchors are passive HTTP servers and do not connect back to the server.
- **Source of Truth:** The central server's registry is the sole source of truth for anchor network locations, physical coordinates, and assigned zones.

---

## Current Features

### 1. Zone & Anchor Registry
- **Manual Anchor Management:** Anchors are registered with `anchor_id`, `base_url` (LAN IP or hostname), physical coordinates $(x, y, \text{floor})$, and assigned `zone_id`.
- **Automatic Identity Verification:** On registration or URL update (`PATCH`), the server queries the anchor's `GET /api/v1/status` endpoint to confirm that the physical anchor reports the identical `anchor_id`.
- **Zone Adjacency Graph:** Configurable adjacency relationships between zones to drive conflict detection and expanding search-area logic.
- **Device Catalog:** Registry of tracked wearable devices (e.g. `KINBEACON-PHONE1`) with soft-delete capabilities.

### 2. High-Performance Transport Layer
- **Concurrent Fan-out:** Uses pooled `httpx.AsyncClient` with HTTP keep-alive and bounded semaphore concurrency (up to 200 simultaneous calls).
- **Resilience & Fault Tolerance:**
  - Strict per-call timeouts (0.5 s connect, 2.0 s read).
  - 1-retry on connect errors and 5xx responses.
  - **Global Deadline Enforcement (5 s):** Unfinished anchor requests are automatically cancelled and marked `TIMEOUT`; searches resolve with whatever data has arrived.
  - **Circuit Breaker:** Automatically trips after 3 consecutive failures, setting the anchor to `DEGRADED` and cooling down for 30 seconds before retrying.

### 3. Pure Zone Identification Engine
Implements a side-effect-free mathematical scoring engine ([app/zoning/engine.py](file:///Users/sarvesh0955/Coding/Kinbeacon/Kinbeacon_central_server/app/zoning/engine.py)):
- **Exponential Recency Decay:** Sighting weights decay with $w_i = \exp(-\Delta t / \tau)$ where $\tau = 20\,\text{s}$.
- **Median Filtering:** Applied across consecutive RSSI samples ($\ge 3$) to eliminate transient multipath spikes.
- **Normalized RSSI Scoring:** RSSI values ($-100$ to $-40$ dBm) map to $[0, 1]$ signal quality $q_a$.
- **Anchor Score:** $s_a = q_a \cdot r_a \cdot \sqrt{\min(1, n_a / 3)}$, factoring in signal quality, recency $r_a$, and sample count $n_a$.
- **Zone Scoring:** $Z_z = \sum \text{top-3 } s_a$ among anchors in that zone (preventing anchor-dense zones from dominating by count alone).
- **Multi-Factor Confidence Metric:**
  $$\text{Confidence} = D \times F \times E \times C \times K$$
  - **$D$ (Dominance):** Probability margin of the top candidate zone ($p_{\text{top}}$).
  - **$F$ (Freshness):** $\exp(-\text{age}_{\text{latest}} / 60\,\text{s})$.
  - **$E$ (Evidence):** $0.5 \cdot \min(1, \text{anchors} / 2) + 0.5 \cdot q_{\text{best}}$ (single anchors are capped at $\le 0.75$).
  - **$C$ (Coverage):** Penalized by the share of unreachable anchors in the target zone and its neighbors.
  - **$K$ (Conflict):** Penalized ($0.6$) if simultaneous non-adjacent candidate conflict is detected.
- **Stale Sightings & Expanding Search Area:**
  - $\le 30\,\text{s}$: Fresh.
  - $30\,\text{s} - 10\,\text{min}$: Marked `STALE`; returns last-known zone and expands search scope to adjacent zones.
  - $> 10\,\text{min}$ or no sightings: Returns `zone=null`, confidence `0.0`, and flag `NOT_SEEN`.
- **Velocity Plausibility Check:** Down-weights older sighting clusters if implied travel speed between anchors exceeds $2.5\,\text{m/s}$.

### 4. Background Services
- **Fleet Health Prober:** Background async worker periodically (every 15 s) pings all enabled anchors via `GET /api/v1/status` to maintain fleet health states (`UP`, `DEGRADED`, `DOWN`).
- **TTL Sighting Purge:** Background worker automatically removes historical searches and sightings older than the 15-minute retention window ($900\,\text{s}$).

### 5. Security & Authentication (Phase 6 Hardening)
- Optional `X-API-Key` header authentication on all `/api/v1` routes (configurable via `API_KEY` in environment).
- Optional `X-Anchor-Key` shared-secret forwarding on outbound anchor requests (`ANCHOR_API_KEY`).

---

## REST API Reference (`/api/v1`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Basic server health and status |
| `GET` | `/api/v1/health` | API version and health status |
| `POST` | `/api/v1/searches` | **Trigger search:** query anchors, aggregate sightings, and compute zone estimate |
| `GET` | `/api/v1/searches/{search_id}` | Retrieve past search outcome by UUID |
| `GET` | `/api/v1/devices/{device_id}/searches` | Retrieve search history for a specific wearable |
| `GET` / `POST` | `/api/v1/zones` | List all zones or create a new zone with boundaries & adjacencies |
| `GET` | `/api/v1/zones/{id}` | Get zone details and adjacent zone IDs |
| `GET` / `POST` | `/api/v1/anchors` | List registered anchors or register a new anchor (with auto-verify) |
| `GET` / `PATCH` / `DELETE`| `/api/v1/anchors/{anchor_id}` | Retrieve, update network/location settings, or delete anchor |
| `POST` | `/api/v1/anchors/{anchor_id}/verify`| Force immediate verification via anchor `/api/v1/status` |
| `GET` | `/api/v1/anchors/status` | Real-time fleet health overview (count of UP, DEGRADED, DOWN) |
| `GET` / `POST` | `/api/v1/devices` | List or register wearable devices |
| `GET` / `PATCH` / `DELETE`| `/api/v1/devices/{device_id}` | Retrieve, update, or soft-delete wearable device |
| `POST` | `/api/v1/admin/seed` | Seed entire venue (zones, adjacencies, anchors, devices) in one payload |

---

## Getting Started

### 1. Requirements & Setup
Python 3.11+ is recommended.

```bash
cd Kinbeacon_central_server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration
All settings can be customized via environment variables or a `.env` file (see [app/core/config.py](file:///Users/sarvesh0955/Coding/Kinbeacon/Kinbeacon_central_server/app/core/config.py)):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./kinbeacon.db` | Async SQLAlchemy database connection string |
| `GLOBAL_SEARCH_DEADLINE_S` | `5.0` | Maximum wait time for all anchors to respond |
| `PER_ANCHOR_READ_TIMEOUT_S`| `2.0` | Read timeout for individual anchor queries |
| `STALE_FRESH_S` | `30.0` | Threshold in seconds before a sighting is considered stale |
| `STALE_MAX_S` | `600.0` | Maximum window (10 min) before sighting expires (`NOT_SEEN`) |
| `API_KEY` | `None` | If set, enforces `X-API-Key` on API requests |
| `ANCHOR_API_KEY` | `None` | If set, sends `X-Anchor-Key` on outbound requests to anchors |

### 3. Running the Server

```bash
# Starts Uvicorn server on port 8000
./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive documentation is automatically generated:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Testing & Verification

Run the automated test suite covering pure zone engine calculations, transport error matrix, and API integration:

```bash
./venv/bin/pytest -v
```

All 17 unit and integration tests validate:
- Zero sightings $\to$ `NOT_SEEN`
- High confidence single-zone resolutions
- Simultaneous conflict flags and penalty factors
- Stale decay and expanding adjacent search zones
- Anchor timeouts, connection refusal, and HTTP 404/5xx handling
- API key authentication guards

---

## Live Simulation Demo

You can run an end-to-end simulation on a single machine using the included Anchor simulator and central server scripts:

1. **Start the Anchor Simulation App (Terminal 1):**
   ```bash
   cd Kinbeacon_anchor
   python3 main.py --mock --port 5001 --anchor-id ANCHOR-LAPTOP-01
   ```

2. **Start the Central Server (Terminal 2):**
   ```bash
   cd Kinbeacon_central_server
   ./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. **Seed the Venue (Terminal 3):**
   ```bash
   cd Kinbeacon_central_server
   ./venv/bin/python scripts/seed_venue.py --anchor-url http://localhost:5001
   ```

4. **Execute Device Search:**
   ```bash
   ./venv/bin/python scripts/run_demo.py --device KINBEACON-PHONE1
   ```

**Sample Output:**
```
================ KinBeacon Search Result ================
 Search ID:       9bbb5e35-d642-4f74-9ec3-8c81ca28ad23
 Device ID:       KINBEACON-PHONE1
 Status:          COMPLETED
 Winning Zone:    Zone 1 (ID: 1)
 Confidence:      0.5495 [MEDIUM]
 Estimated Pos:   x=10.0m, y=10.0m, floor=0
 Age:             7.16s
 Flags:           SINGLE_ANCHOR

 Fleet Summary:
  Targeted: 1, Responded: 1, Timed Out: 0, Failed: 0

 Anchor Evidence:
  * Anchor ANCHOR-LAPTOP-01: 6 samples, RSSI=-55.7 dBm, Score=0.516, Age=7.2s

 Roundtrip API Latency: 46.21 ms
=========================================================
```
