import asyncio
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import ZONE_HISTORY_MINUTES, Settings, settings as global_settings
from app.core.logging import logger
from app.models.entities import Anchor
from app.schemas.anchor import AnchorVerificationResult
from app.transport.base import AnchorTransport
from app.transport.models import AnchorSearchResult
from app.zoning.models import RawSighting


def parse_timestamp(ts_str: Any) -> Optional[datetime]:
    """Parse ISO 8601 UTC timestamp or epoch timestamp."""
    if not ts_str:
        return None
    if isinstance(ts_str, (int, float)):
        return datetime.fromtimestamp(ts_str, tz=timezone.utc)
    if isinstance(ts_str, str):
        # Handle 'Z' suffix
        cleaned = ts_str.strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
        try:
            # Try parsing as float epoch
            return datetime.fromtimestamp(float(cleaned), tz=timezone.utc)
        except ValueError:
            return None
    return None


class HttpAnchorTransport(AnchorTransport):
    """HTTP client communicating with anchor REST APIs."""

    def __init__(self, config: Optional[Settings] = None, client: Optional[httpx.AsyncClient] = None):
        self.cfg = config or global_settings
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=self.cfg.per_anchor_connect_timeout_s,
                read=self.cfg.per_anchor_read_timeout_s,
                write=self.cfg.per_anchor_read_timeout_s,
                pool=self.cfg.per_anchor_connect_timeout_s,
            ),
            limits=httpx.Limits(
                max_connections=self.cfg.max_anchor_concurrency,
                max_keepalive_connections=50,
            ),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _query_single_anchor(
        self,
        anchor: Anchor,
        device_id: str,
        search_id: Optional[str],
        semaphore: asyncio.Semaphore,
        now: datetime,
    ) -> AnchorSearchResult:
        base_url = anchor.base_url.rstrip("/")
        url = f"{base_url}/api/v1/search"
        headers = {"Content-Type": "application/json"}
        if search_id:
            headers["X-Request-ID"] = search_id
        if self.cfg.anchor_api_key:
            headers["X-Anchor-Key"] = self.cfg.anchor_api_key

        payload = {"device_id": device_id}

        async with semaphore:
            t0 = time.perf_counter()
            retries = 1
            last_error: Optional[str] = None
            response: Optional[httpx.Response] = None

            for attempt in range(retries + 1):
                try:
                    response = await self._client.post(url, json=payload, headers=headers)
                    if response.status_code >= 500 and attempt < retries:
                        await asyncio.sleep(0.05)
                        continue
                    break
                except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                    last_error = f"Connect error: {e}"
                    if attempt < retries:
                        await asyncio.sleep(0.05)
                        continue
                    break
                except httpx.ReadTimeout:
                    latency_ms = (time.perf_counter() - t0) * 1000.0
                    return AnchorSearchResult(
                        anchor_id=anchor.anchor_id,
                        outcome="TIMEOUT",
                        latency_ms=round(latency_ms, 2),
                        error="Read timeout",
                    )
                except httpx.RequestError as e:
                    last_error = f"Request error: {e}"
                    break

            latency_ms = (time.perf_counter() - t0) * 1000.0

            if response is None:
                return AnchorSearchResult(
                    anchor_id=anchor.anchor_id,
                    outcome="ERROR",
                    latency_ms=round(latency_ms, 2),
                    error=last_error or "Network request failed",
                )

            # Defensive 404 treated as EMPTY
            if response.status_code == 404:
                return AnchorSearchResult(
                    anchor_id=anchor.anchor_id,
                    outcome="EMPTY",
                    http_status=404,
                    latency_ms=round(latency_ms, 2),
                )

            if response.status_code != 200:
                return AnchorSearchResult(
                    anchor_id=anchor.anchor_id,
                    outcome="ERROR",
                    http_status=response.status_code,
                    latency_ms=round(latency_ms, 2),
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                )

            try:
                data = response.json()
            except Exception as e:
                return AnchorSearchResult(
                    anchor_id=anchor.anchor_id,
                    outcome="ERROR",
                    http_status=200,
                    latency_ms=round(latency_ms, 2),
                    error=f"Malformed JSON: {e}",
                )

            # Verify payload device_id matches requested
            resp_dev = data.get("device_id")
            if resp_dev and resp_dev != device_id:
                return AnchorSearchResult(
                    anchor_id=anchor.anchor_id,
                    outcome="ERROR",
                    http_status=200,
                    latency_ms=round(latency_ms, 2),
                    error=f"Device ID mismatch: requested '{device_id}', got '{resp_dev}'",
                )

            # Check anchor_id mismatch
            resp_anchor = data.get("anchor_id")
            if resp_anchor and resp_anchor != anchor.anchor_id:
                logger.warning(
                    "Anchor ID mismatch for %s: reported '%s'",
                    anchor.anchor_id,
                    resp_anchor,
                )

            records = data.get("records", [])
            if not records:
                return AnchorSearchResult(
                    anchor_id=anchor.anchor_id,
                    outcome="EMPTY",
                    http_status=200,
                    latency_ms=round(latency_ms, 2),
                )

            # Parse and validate sightings
            parsed_sightings: List[RawSighting] = []
            dropped = 0
            max_age_s = max(ZONE_HISTORY_MINUTES * 60, self.cfg.stale_max_s)

            for r in records:
                rssi = r.get("rssi")
                ts_raw = r.get("timestamp")
                if rssi is None or ts_raw is None:
                    dropped += 1
                    continue
                if not isinstance(rssi, (int, float)) or rssi < -120 or rssi > 0:
                    dropped += 1
                    continue

                ts = parse_timestamp(ts_raw)
                if ts is None:
                    dropped += 1
                    continue

                future_skew = (ts - now).total_seconds()
                if future_skew > self.cfg.max_future_skew_s:
                    dropped += 1
                    continue

                age = (now - ts).total_seconds()
                if age > max_age_s:
                    dropped += 1
                    continue

                parsed_sightings.append(
                    RawSighting(
                        anchor_id=anchor.anchor_id,
                        observed_at=ts,
                        rssi=int(rssi),
                    )
                )

            outcome = "OK" if parsed_sightings else "EMPTY"
            return AnchorSearchResult(
                anchor_id=anchor.anchor_id,
                outcome=outcome,
                http_status=200,
                latency_ms=round(latency_ms, 2),
                sightings=parsed_sightings,
                dropped_count=dropped,
            )

    async def search_all(
        self,
        device_id: str,
        anchors: List[Anchor],
        search_id: Optional[str] = None,
        deadline_s: Optional[float] = None,
    ) -> Dict[str, AnchorSearchResult]:
        if not anchors:
            return {}

        now = datetime.now(timezone.utc)
        deadline = deadline_s or self.cfg.global_search_deadline_s
        semaphore = asyncio.Semaphore(self.cfg.max_anchor_concurrency)

        tasks = [
            asyncio.create_task(
                self._query_single_anchor(anchor, device_id, search_id, semaphore, now),
                name=f"search-{anchor.anchor_id}",
            )
            for anchor in anchors
        ]

        done, pending = await asyncio.wait(
            tasks,
            timeout=deadline,
            return_when=asyncio.ALL_COMPLETED,
        )

        results: Dict[str, AnchorSearchResult] = {}

        # Collect finished tasks
        for task in done:
            res = task.result()
            results[res.anchor_id] = res

        # Cancel and record pending tasks as TIMEOUT
        for task in pending:
            task.cancel()
            anchor_name = task.get_name().replace("search-", "")
            results[anchor_name] = AnchorSearchResult(
                anchor_id=anchor_name,
                outcome="TIMEOUT",
                error=f"Exceeded global deadline of {deadline}s",
            )

        return results

    async def verify_anchor(self, anchor: Anchor) -> AnchorVerificationResult:
        base_url = anchor.base_url.rstrip("/")
        url = f"{base_url}/api/v1/status"
        headers = {}
        if self.cfg.anchor_api_key:
            headers["X-Anchor-Key"] = self.cfg.anchor_api_key
        try:
            resp = await self._client.get(url, headers=headers, timeout=3.0)
            if resp.status_code != 200:
                return AnchorVerificationResult(
                    anchor_id=anchor.anchor_id,
                    verified=False,
                    status_code=resp.status_code,
                    message=f"Anchor returned HTTP {resp.status_code}",
                )
            data = resp.json()
            reported_id = data.get("anchor_id")
            scanner_status = data.get("ble_scanner")

            if reported_id != anchor.anchor_id:
                logger.warning(
                    "Anchor '%s' reported anchor_id '%s'",
                    anchor.anchor_id,
                    reported_id,
                )
                return AnchorVerificationResult(
                    anchor_id=anchor.anchor_id,
                    verified=True,
                    status_code=200,
                    reported_anchor_id=reported_id,
                    ble_scanner=scanner_status,
                    message=f"Verified (reported remote ID '{reported_id}')",
                )

            return AnchorVerificationResult(
                anchor_id=anchor.anchor_id,
                verified=True,
                status_code=200,
                reported_anchor_id=reported_id,
                ble_scanner=scanner_status,
                message="Anchor verified successfully",
            )
        except Exception as e:
            return AnchorVerificationResult(
                anchor_id=anchor.anchor_id,
                verified=False,
                message=f"Connection failed: {e}",
            )

    async def check_health(self, anchor: Anchor) -> str:
        base_url = anchor.base_url.rstrip("/")
        url = f"{base_url}/api/v1/status"
        headers = {}
        if self.cfg.anchor_api_key:
            headers["X-Anchor-Key"] = self.cfg.anchor_api_key
        try:
            resp = await self._client.get(url, headers=headers, timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ble_scanner") == "running":
                    return "UP"
                return "DEGRADED"
            return "DEGRADED"
        except Exception:
            return "DOWN"
