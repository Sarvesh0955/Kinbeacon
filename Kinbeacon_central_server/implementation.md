# KinBeacon Central Server: Implementation Plan

**Scope:** central server for device and anchor registry, guardian search, anchor communication, log aggregation, and zone identification. Plan only; no code.

**Assumptions**
- Anchors (laptops running the Anchor Simulation App) are **separate devices** that run an **HTTP server** and expose the search endpoint below. The central server is a client of those endpoints.
- **Anchors are registered manually.** An admin adds each anchor's `anchor_id`, `base_url`, location, and zone through the server's API or a seed file. Anchors never register themselves.
- Everything sits on one private venue LAN; no public internet needed for the core path.
- Priority is a practical working simulation, not production hardening.

**Anchor contract (given):**

```bash
curl -X POST http://localhost:5000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"device_id": "KINBEACON-PHONE1"}'
```

- The request body contains only `device_id`.
- The **anchor API is confirmed** from the Anchor Simulation App README (section 5): `POST /api/v1/search` returns `records` plus `record_count`, an unseen device returns `200` with an empty list, and `GET /api/v1/status` reports anchor health. Each anchor keeps a 15-minute rolling window.

---

## 1. Recommended Technology Stack

| Concern | Choice | Why |
|---|---|---|
| Language / API | Python 3.11+, FastAPI, Uvicorn | Async-native, auto OpenAPI docs, fast to build |
| Validation | Pydantic v2 | Shared schemas for REST API and anchor response parsing |
| Anchor I/O | `httpx.AsyncClient` (pooled, keep-alive) + `asyncio` | Concurrent fan-out with per-call timeouts |
| DB | SQLite via SQLAlchemy 2.0 (async) | Zero setup; Postgres by changing the URL |
| Migrations | Alembic (or `create_all` for the simulation) | Optional early on |
| Config | `pydantic-settings` + env vars | All algorithm and network constants tunable without code changes |
| Testing | pytest, pytest-asyncio, respx, hypothesis, a fake anchor server | Mocked anchors, property tests on scoring |

Redis, Kafka, and a broker are excluded for now. A transport interface (section 5.6) keeps MQTT or WebSocket possible later without touching the aggregator or zone engine.

---

## 2. Network Topology

```
 [Anchor laptop 1  :5000]──┐
 [Anchor laptop 2  :5000]──┼── Wi-Fi router / switch ──── [Central Server :8000]
 [Anchor laptop N  :500x]──┘     (private venue LAN)             │
                                                         Guardian App / Staff dashboard
```

- **Direction:** the server initiates every search call to each anchor's `base_url`. Anchors do not connect to the server.
- Each anchor's `base_url` is stored in the registry (e.g. `http://192.168.1.21:5000`). `localhost` only works if the server and that anchor run on the **same** machine, so use LAN IPs for separate devices.
- Anchors must **bind to `0.0.0.0`** (not only `127.0.0.1`) and allow the port through the laptop firewall.
- Anchor IPs must be stable: use DHCP reservations or static IPs. If an IP changes, the registry entry must be updated (see 5.4).
- Several simulated anchors on one laptop need different ports.

---

## 3. Architecture and Data Flow

A modular monolith. The zone engine is a **pure module** (no I/O) so it is testable and swappable.

```
kinbeacon_server/
  app/
    main.py
    core/          config, logging, errors, auth stub
    api/           routers: zones, devices, anchors, searches, health
    schemas/       Pydantic request/response + anchor response schema
    models/        SQLAlchemy ORM
    repositories/  DB access
    services/      registry_service, search_service, aggregation_service, health_service
    transport/     base.py (AnchorTransport), http.py, mock.py
    zoning/        config, scoring, confidence, conflicts, engine
  tests/
  scripts/         seed_venue, run_demo
```

**Search flow**

```
Guardian App ──POST /api/v1/searches {device_id}──► API layer
  1. Validate device; create Search row (RUNNING)
  2. SearchService selects active anchors from the registry
  3. HttpTransport fans out: POST {base_url}/api/v1/search {"device_id": ...}
       concurrent, semaphore-bounded, per-anchor timeout, 1 retry, global deadline
  4. AggregationService: parse, validate, dedupe, sort chronologically,
       record per-anchor outcome (OK / EMPTY / TIMEOUT / ERROR / SKIPPED)
  5. ZoneEngine (pure): sightings + anchor metadata + now → ZoneEstimate
  6. Persist sightings, anchor results, estimate; return response
```

---

## 4. Database Schema

| Table | Key columns | Notes |
|---|---|---|
| `zones` | `id`, `name`, `centroid_x/y`, `metadata` | |
| `zone_adjacency` | `zone_a_id`, `zone_b_id` | Drives conflict checks and search-area expansion |
| `anchors` | `id`, `anchor_id` (unique), `zone_id` FK, `x`, `y`, `floor`, **`base_url`**, `enabled`, `verified`, `verified_at`, `verify_note`, `health_state` (UP/DEGRADED/DOWN/UNKNOWN), `last_success_at`, `last_failure_at`, `consecutive_failures`, `circuit_open_until`, `clock_offset_ms`, `metadata` | `is_active` is derived: enabled and circuit not open |
| `devices` | `id`, `device_id` (unique), `display_name`, `guardian_ref`, `status`, `metadata` | Wearable registry, e.g. `KINBEACON-PHONE1` |
| `searches` | `id` (uuid), `device_id` FK, `requested_by`, `status`, `started_at`, `completed_at`, `anchors_targeted`, `anchors_responded` | Status: RUNNING, COMPLETED, PARTIAL, FAILED |
| `search_anchor_results` | `search_id`, `anchor_id`, `outcome`, `http_status`, `latency_ms`, `sightings_count`, `dropped_count`, `error` | Outcome: OK, EMPTY, TIMEOUT, ERROR, SKIPPED |
| `sightings` | `search_id`, `anchor_id`, `device_id`, `observed_at`, `rssi` | Index `(search_id, observed_at)`; dedupe key `(anchor_id, device_id, observed_at)` |
| `zone_estimates` | `search_id`, `zone_id`, `rank`, `score`, `probability`, `confidence`, `flags`, `evidence` (JSON) | Top-N candidates per search |

**Relationships:** zone → many anchors; device → many searches; search → many anchor results, sightings, and estimates.

**Retention:** a background task purges sightings and searches older than a configurable TTL, matching the deck's limited-retention principle.

---

## 5. Anchor Communication (HTTP)

### 5.1 Request to each anchor

- `POST {base_url}/api/v1/search` with header `Content-Type: application/json` and body `{"device_id": "<id>"}`.
- Send **only `device_id`**. The simulator documents no other request fields (no `since` or `max_results`), so the server sends none and applies its own time window to the results.
- Optional `X-Request-ID` header carrying the `search_id` for log correlation. Harmless to ignore.
- A `TokenResolver` hook sits before the transport. The simulation passes the raw `device_id`; later it can send the current rotating token, per the deck's privacy design.

### 5.2 Anchor response (confirmed sample)

Sample from the simulator:

```
200 OK
{ "anchor_id": "ANCHOR-LAPTOP-01",
  "device_id": "KINBEACON-PHONE1",
  "record_count": 3,
  "records": [ { "rssi": -58, "timestamp": "2026-11-19T00:15:30.123Z" }, ... ] }
```

Parser rules (all in one adapter, `transport/http.py` plus `schemas/anchor.py`):
- Timestamps are ISO 8601 UTC with milliseconds and a `Z` suffix; parse and normalise to UTC. Epoch values stay accepted via config as a fallback.
- Sightings are read from `records` (key is configurable). `rssi` is an integer in dBm.
- `record_count` is cross-checked against the list length; a mismatch is logged, not fatal.
- `200` with `record_count: 0` and an empty `records` list means **EMPTY** (device not heard within the anchor's 15-minute window), not an error. A `404` is also treated as EMPTY, defensively.
- `5xx`, connection refused, or invalid JSON means **ERROR**; no response in time means **TIMEOUT**.
- The registry entry that was called identifies the anchor. If the payload's `anchor_id` differs from the registry's `anchor_id`, log a warning (likely misconfiguration) and keep the registry mapping.
- If the payload's `device_id` differs from the one requested, treat that response as **ERROR** and discard it.

**Timestamps:** the README's sample times are illustrative. Real scanning stamps records with the laptop's clock, so all machines need NTP. The server drops timestamps beyond a configurable `MAX_FUTURE_SKEW` (default a few seconds). Check once that `--mock` mode also stamps real time; if it replays fixed times, every sighting would be silently rejected.

**Payload size:** the anchor returns *every* record in its 15-minute window, and there is no `since` or `max_results`. A phone advertising every 100–500 ms can yield thousands of records per anchor per search. The server therefore caps the response size it will read (e.g. 2 MB), parses only records inside its own analysis window (about 5 min), and reduces them per anchor (latest timestamp, count, smoothed RSSI) before use. Only a capped number of the most recent raw samples per anchor (e.g. 50) are persisted in `sightings`; the rest are summarised.

If field names change later, only this adapter (`transport/http.py` plus `schemas/anchor.py`) changes.

### 5.3 Fan-out and aggregation rules

- Targets: all anchors where `enabled` and the circuit is not open.
- One shared `httpx.AsyncClient` with connection pooling and keep-alive; `asyncio.gather` over per-anchor tasks.
- Bounded concurrency (semaphore around 200), per-anchor timeout (about 2 s: 0.5 s connect, 2 s read), **one retry** on connect errors and 5xx only, and a **global deadline** (about 5 s). When the deadline hits, pending calls are cancelled and the search uses whatever has arrived.
- Validate rows: drop RSSI outside −120..0, timestamps in the future (beyond a small skew tolerance) or older than the window, and malformed rows. Record the drop count per anchor.
- Dedupe by `(anchor_id, device_id, observed_at)`, then sort all sightings chronologically.
- Staged mode (optional): query the last-known zone's anchors and neighbours first, then everyone if there is no hit. This reduces calls at scale.

### 5.4 Anchor registration, health, and the circuit breaker

Because anchors are passive HTTP servers, **the registry is the source of truth** for where anchors are.

- **Registration is manual only.** An admin creates each anchor with `POST /anchors` or loads a venue JSON via `/admin/seed`, supplying `anchor_id`, `base_url`, `x`, `y`, and `zone`. Anchors never register themselves, and an unregistered anchor is never called.
- **Verification on registration:** after an anchor is created or edited, the server calls `GET {base_url}/api/v1/status` and checks that the returned `anchor_id` matches the registry entry. The outcome is stored as `verified` with a reason. An unverified anchor is flagged, but an admin can still enable it.
- **IP changes are manual too:** if a laptop's IP changes, an admin updates `base_url` with `PATCH /anchors/{anchor_id}`, which re-runs verification. Fixed IPs or DHCP reservations avoid this.
- **Health via the status endpoint:** a background prober calls `GET /api/v1/status` on each anchor every ~15 s. `ble_scanner: running` means UP; reachable with the scanner not running is DEGRADED; no response is DOWN. Health is also updated passively from every search outcome.
- **Circuit breaker:** after N consecutive failures (about 3) the anchor goes DEGRADED and is skipped for a cooldown (about 30 s), then retried. Skipped anchors are still reported as `unreachable` so confidence can be penalised.
- **Clock skew:** the server computes sighting age with its own clock. If the response or an HTTP `Date` header carries the anchor's time, store `clock_offset_ms` per anchor and correct for it. Run NTP on every machine.

### 5.5 Security (demo-level)

- The simulator has **no authentication** today, so its API is open to anyone on the LAN. Restrict each anchor's port to the server's IP at the laptop firewall and keep anchors on the isolated venue network.
- A shared-secret header (`X-Anchor-Key`) is a later step that needs a small change in the simulator; HTTPS and mTLS come after that.

### 5.6 Transport interface and extensibility

```
AnchorTransport:
  search_all(search_request, anchors, deadline) -> per-anchor results
```

- Implementations: `HttpTransport` (real, now) and `MockTransport` (in-process, for tests). `MqttTransport` or `WebSocketTransport` could be added later with no change to the aggregator or zone engine.
- All HTTP specifics (paths, headers, retry rules, response parsing) stay inside `transport/http.py`; endpoint paths live in one constants module.
- Version the anchor API path (`/api/v1/`). When the contract changes, add `v2` support in the adapter and keep v1 working during migration.
- New data later (battery, telemetry, SOS) means new endpoints on anchors, called by the same transport; the registry table gets columns, not a redesign.

**Why a future switch to push (MQTT) might be worth it:** with HTTP the server makes one call per anchor per search, so 500–1,000 anchors means 500–1,000 requests per search, the server must know every anchor address, and anchors behind NAT are unreachable. That is fine for a laptop simulation. The transport interface keeps that migration cheap.

---

## 6. REST API Design (`/api/v1`)

This is the **server's** API, used by the Guardian App, staff dashboard, and admin. Do not confuse it with the anchors' `/api/v1/search` endpoint.

| Method | Path | Purpose |
|---|---|---|
| POST / GET | `/zones`, `/zones/{id}` | Zone and adjacency registration |
| POST / GET / PATCH / DELETE | `/devices`, `/devices/{device_id}` | Wearable registry (DELETE is soft) |
| POST / GET / PATCH / DELETE | `/anchors`, `/anchors/{anchor_id}` | **Manual** anchor registry: `anchor_id`, `base_url`, location, zone. POST and PATCH trigger verification |
| POST | `/anchors/{anchor_id}/verify` | Re-check the anchor through its `/api/v1/status` endpoint |
| **POST** | **`/searches`** | Body: `device_id`, optional `max_age_s`, `requested_by`. Blocks up to the global deadline and returns the full result |
| GET | `/searches/{search_id}`, `/devices/{device_id}/searches` | Result retrieval and history |
| GET | `/health`, `/anchors/status` | Server and anchor-fleet health |
| POST | `/admin/seed` | Load a venue JSON (zones, anchors with `base_url`, devices) |

**Search response:** `search_id`, `status`, `zone {id, name}`, `confidence` (0–1) and `confidence_label`, `last_seen_at`, `age_s`, `candidates[]` (zone, score, probability), `evidence[]` (anchor, smoothed RSSI, last seen, count), `flags[]` (`STALE`, `CONFLICT`, `SINGLE_ANCHOR`, `PARTIAL_COVERAGE`, `NOT_SEEN`), and `anchors {targeted, responded, timed_out, failed, unreachable[]}`.

**Error handling**
- Unknown device: 404.
- No active anchors: 503.
- Partial anchor failure: 200 with `status=PARTIAL`.
- No sightings: 200 with `zone=null`, `confidence=0`, flag `NOT_SEEN`.

---

## 7. Zone Identification Algorithm

All constants are config-driven. Defaults are starting points to tune against simulation results.

**Step 1: Per-anchor summary** (window ≈ 5 min, τ = 20 s, RSSI normalised over −100..−40 dBm)
- Sighting weight: `w_i = exp(−age_i / τ)`
- Weighted signal strength: `q_a = Σ w_i·norm(rssi_i) / Σ w_i`, after a median filter when ≥ 3 samples
- Recency: `r_a = exp(−age_latest / τ)`
- Anchor score: `s_a = q_a · r_a · sqrt(min(1, n_a / 3))`

**Step 2: Zone score**
- `Z_z` = sum of the top-3 `s_a` among that zone's anchors (the cap stops anchor-dense zones winning by count).
- Probability: `p_z = Z_z / Σ Z`.
- Optional: score-weighted centroid of top anchors for an approximate (x, y).

**Step 3: Confidence** = `D × F × E × C × K`
- **D** (dominance) = `p_top`.
- **F** (freshness) = `exp(−age_s / 60)`.
- **E** (evidence) = `0.5·min(1, anchors_in_zone/2) + 0.5·q_best`; a single anchor cannot give high confidence.
- **C** (coverage) = `1 − 0.5 × (share of unreachable anchors in the top zone and its neighbours)`.
- **K** (conflict) = 0.6 if a conflict is flagged, else 1.
- Labels: HIGH ≥ 0.7, MEDIUM 0.4–0.7, LOW < 0.4.

**Step 4: Conflicting sightings**
- *Simultaneous conflict:* top two zones non-adjacent, scores within 60% of each other, strongest sightings within 5 s. Sets `CONFLICT`, applies K, returns both zones in `candidates`.
- *Speed plausibility:* if the distance between two time-ordered sighting clusters (from anchor x, y) divided by Δt exceeds max speed (~2–3 m/s), down-weight the older cluster.
- *Recency precedence:* exponential decay makes the newest cluster dominate; older evidence mainly breaks ties.

**Step 5: Stale handling**
- Fresh: ≤ 30 s.
- Stale: 30 s to 10 min. Return last-known zone with `STALE`, decayed confidence, and an **expanding search area** (zone plus adjacent zones, growing with `age × v_max`).
- Expired: > 10 min or no sightings. Return `zone=null`, `NOT_SEEN`.

---

## 8. Implementation Phases

| Phase | Deliverable | Exit criterion |
|---|---|---|
| 0 | Project skeleton, config, DB session, `/health` | Server boots, tests run |
| 1 | Zones, anchors (with `base_url`), devices CRUD plus venue seed script | Seed loads a sample venue |
| 2 | Transport interface, `MockTransport`, `HttpTransport`, response adapter, health prober, circuit breaker | Fan-out against a **fake anchor server** works, including failures |
| 2.5 | Verify against one real simulator laptop over the LAN | Server on machine A gets sightings from anchor on machine B |
| 3 | `POST /searches`, fan-out, aggregation, persistence | Partial failure and timeouts produce `PARTIAL` results |
| 4 | Zone engine (pure) with fixture scenarios | Golden scenarios pass |
| 5 | Integration with several simulator laptops | Simulated moving device resolves to the correct zone end-to-end |
| 6 | Hardening: structured logs, purge job, API-key header, constant tuning, demo script | Repeatable demo run |

---

## 9. Testing Strategy

- **Unit (zone engine) golden scenarios:** clear single zone; border between two zones; stale-only; simultaneous conflict; single-anchor evidence; no sightings; unreachable anchors adjacent to the best zone.
- **Property tests (hypothesis):** confidence stays in [0, 1]; confidence never increases as sightings age; probabilities sum to 1.
- **Transport tests (respx plus a fake anchor app):** timeout, 404, 500s, connection refused, invalid JSON, wrong field names, slow anchors, retry and circuit-breaker behaviour, and the global deadline cancelling stragglers.
- **API tests:** `httpx.AsyncClient` against in-memory SQLite, covering the error matrix in section 6.
- **Scale test:** 500–1,000 fake anchors (one lightweight async server on many ports, or a mock transport with injected latency). Check completion within the deadline and connection-pool behaviour.
- **End-to-end:** deterministic seeded simulator path across zones; measure top-1 zone accuracy and time-to-correct-zone against ground truth.

---

## 10. Potential Limitations

- **Server must reach every anchor.** NAT, firewalls, laptop sleep, and changing IPs all break calls. Mitigated by the status-endpoint health prober, fixed IPs, and re-verification whenever an admin updates a `base_url`.
- **Per-search load grows with anchor count** (one HTTP call each). Staged mode and a future push model are the mitigations.
- **Pull-only data:** the server learns about sightings only when it asks. The deck describes anchors forwarding sightings continuously; an optional ingest endpoint on the server (`POST /anchors/{id}/sightings`) with a recent-sightings cache could be added without disturbing this design.
- **Unconfirmed response schema** may need adapter tweaks.
- Real RSSI is noisy (body blocking, multipath), so output is **zone-level** only. Simulated RSSI will flatter the algorithm.
- Clock skew is tolerated via a small allowance and per-anchor offset, not fully corrected.
- Rotating-token resolution, authentication, and offline identity are stubbed.
- Single server instance with SQLite: limited write concurrency and no HA.
- Thresholds (τ, stale limits, speed) are educated guesses until tuned on real pilot data.

---

## 11. Demo Setup: Laptops as HTTP Anchors

- Run the simulator on each laptop with `--host 0.0.0.0` (the default) on a known port, and give every anchor a unique `--anchor-id`. The registry's `anchor_id` must match it exactly.
- On macOS, port 5000 is often taken by the AirPlay Receiver. If the anchor fails to bind, start it with `--port 5001` and use that port in `base_url`.
- One laptop has one Bluetooth radio, so only one anchor per laptop can scan for real. Several anchors on one laptop make sense only in `--mock` mode, and each then needs its own `--port`, `--anchor-id`, **and** `--db` file so they don't share a database.
- Reserve or fix each laptop's IP; record it as `base_url` in the seed file, e.g. `http://192.168.1.21:5000`.
- Open the port in each laptop's firewall (ideally only to the server's IP).
- Use a router with Wi-Fi client isolation **off**; avoid campus or corporate networks that block device-to-device traffic.
- Keep laptops awake and plugged in; sleep makes an anchor TIMEOUT, which is a good failure-mode demo.
- Test from the server machine first: `curl -X POST http://<anchor-ip>:5000/api/v1/search -H "Content-Type: application/json" -d '{"device_id": "KINBEACON-PHONE1"}'`. If that works, the server's call will too.
- Sync clocks with NTP on all machines.
- Register wearables using the exact BLE advertised name (e.g. `KINBEACON-PHONE1`). The anchor matches on that name, so the server's `device_id` must equal it, including the `KINBEACON-` prefix.
- Use real BLE for the live demo. For repeatable zone-accuracy tests, use `--mock` with a deterministic scenario, if the mock generator can be made seedable.

---

## 12. Demo Seed (Single Anchor, Single Zone)

**Layout assumptions**
- One zone ("Zone 1") shaped as a **square**, with the **anchor at its center**.
- Coordinates are **metres**, origin at the square's south-west corner, x pointing east and y north, floor 0. Square side defaults to **20 m** (configurable; the real size is not given).
- Zone 1 centroid is therefore (10, 10), and the anchor sits at (10, 10). Zone bounds and side length are stored in the zone's `metadata`.

**Seed file contents** (loaded by `scripts/seed_venue` or `POST /admin/seed`):

```json
{
  "zones": [
    { "id": 1, "name": "Zone 1",
      "centroid": { "x": 10, "y": 10 },
      "metadata": { "shape": "square", "side_m": 20,
                    "bounds": { "x_min": 0, "y_min": 0, "x_max": 20, "y_max": 20 } },
      "adjacent_to": [] }
  ],
  "anchors": [
    { "anchor_id": "ANCHOR-LAPTOP-01",
      "base_url": "http://<laptop-ip>:5000",
      "zone_id": 1, "x": 10, "y": 10, "floor": 0, "enabled": true }
  ],
  "devices": [
    { "device_id": "KINBEACON-PHONE1", "display_name": "Demo phone 1" }
  ]
}
```

- `anchor_id` must equal the simulator's `--anchor-id` (default `ANCHOR-LAPTOP-01`).
- Replace `<laptop-ip>` with the laptop's LAN IP (or `localhost` when the server runs on the same machine). Use the port the simulator actually bound.
- On seeding, the server verifies the anchor through `/api/v1/status` (section 5.4).

**What this seed does and does not exercise**

| Behaviour with one anchor in one zone | Consequence |
|---|---|
| Any sighting resolves to Zone 1; no sighting gives `NOT_SEEN` | The pipeline, parsing, recency decay, and stale handling are all testable end to end |
| Dominance D = 1 (only one zone) | Zone choice is trivial |
| `SINGLE_ANCHOR` is always flagged; evidence E ≤ 0.75 | Confidence tops out near 0.75 even for a perfect fresh signal. With the sample RSSI of about −58 dBm, E is about 0.6, so expect MEDIUM labels; HIGH needs a very strong, very recent signal |
| Anchor at the center | The estimated position is the anchor's own (10, 10). Zone-level only. An optional RSSI-based proximity band (near / mid / far) can be reported, but not a direction |
| No adjacent zones | Stale search-area expansion stays inside Zone 1 |
| No competing zones | Conflict detection, speed plausibility, cross-zone ranking, and staged fan-out cannot run with this seed |

Those untested paths are covered by **synthetic multi-zone fixtures** in the zone-engine unit tests (section 9). When more laptops are available, add a second seed file (for example `venue_multi.json` with several squares and one anchor per center) to exercise them live.

---
