import math
from datetime import datetime, timezone
from typing import List, Optional
from app.zoning.models import AnchorMetadata, AnchorSummary, RawSighting


def normalize_rssi(rssi: float, rssi_min: float = -100.0, rssi_max: float = -40.0) -> float:
    """Linearly normalise RSSI from [rssi_min, rssi_max] into [0, 1]."""
    if rssi <= rssi_min:
        return 0.0
    if rssi >= rssi_max:
        return 1.0
    return (rssi - rssi_min) / (rssi_max - rssi_min)


def apply_median_filter(rssi_values: List[int]) -> List[float]:
    """Applies a 3-tap median filter when >= 3 samples."""
    n = len(rssi_values)
    if n < 3:
        return [float(x) for x in rssi_values]
    filtered: List[float] = []
    for i in range(n):
        window = rssi_values[max(0, i - 1) : min(n, i + 2)]
        window_sorted = sorted(window)
        mid = len(window_sorted) // 2
        if len(window_sorted) % 2 == 1:
            filtered.append(float(window_sorted[mid]))
        else:
            filtered.append((window_sorted[mid - 1] + window_sorted[mid]) / 2.0)
    return filtered


def summarize_anchor_sightings(
    anchor_id: str,
    sightings: List[RawSighting],
    anchor_meta: Optional[AnchorMetadata],
    now: datetime,
    tau: float = 20.0,
    rssi_min: float = -100.0,
    rssi_max: float = -40.0,
) -> Optional[AnchorSummary]:
    """Computes decay-weighted signal strength, recency, and anchor score."""
    if not sightings:
        return None

    # Ensure now is UTC-aware
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Sort sightings chronologically
    sorted_sightings = sorted(sightings, key=lambda s: s.observed_at)
    latest_sighting = sorted_sightings[-1]

    # Normalize observed_at timezone
    latest_time = latest_sighting.observed_at
    if latest_time.tzinfo is None:
        latest_time = latest_time.replace(tzinfo=timezone.utc)

    age_latest = max(0.0, (now - latest_time).total_seconds())

    # Raw RSSIs with optional median filtering
    raw_rssis = [s.rssi for s in sorted_sightings]
    smoothed_rssis = apply_median_filter(raw_rssis)

    # Weights w_i = exp(-age_i / tau)
    total_w = 0.0
    weighted_norm_sum = 0.0
    weighted_raw_sum = 0.0

    for s, smoothed_val in zip(sorted_sightings, smoothed_rssis):
        s_time = s.observed_at
        if s_time.tzinfo is None:
            s_time = s_time.replace(tzinfo=timezone.utc)
        age_i = max(0.0, (now - s_time).total_seconds())
        w_i = math.exp(-age_i / tau)
        norm_v = normalize_rssi(smoothed_val, rssi_min, rssi_max)
        weighted_norm_sum += w_i * norm_v
        weighted_raw_sum += w_i * smoothed_val
        total_w += w_i

    q_a = (weighted_norm_sum / total_w) if total_w > 0 else 0.0
    smoothed_rssi = (weighted_raw_sum / total_w) if total_w > 0 else float(latest_sighting.rssi)

    # Recency factor r_a = exp(-age_latest / tau)
    r_a = math.exp(-age_latest / tau)

    # Sighting count factor sqrt(min(1.0, n_a / 3))
    n_a = len(sorted_sightings)
    count_factor = math.sqrt(min(1.0, n_a / 3.0))

    # Anchor score s_a = q_a * r_a * count_factor
    s_a = q_a * r_a * count_factor

    zone_id = anchor_meta.zone_id if anchor_meta else None
    x = anchor_meta.x if anchor_meta else 0.0
    y = anchor_meta.y if anchor_meta else 0.0
    floor = anchor_meta.floor if anchor_meta else 0

    return AnchorSummary(
        anchor_id=anchor_id,
        zone_id=zone_id,
        count=n_a,
        latest_timestamp=latest_time,
        age_s=age_latest,
        smoothed_rssi=smoothed_rssi,
        normalized_rssi=q_a,
        anchor_score=s_a,
        x=x,
        y=y,
        floor=floor,
    )
