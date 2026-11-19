import math
from typing import Dict, List, Optional, Set, Tuple
from app.zoning.models import AnchorSummary, ZoneScore


def check_speed_plausibility(
    anchor_summaries: List[AnchorSummary],
    max_speed_mps: float = 2.5,
) -> List[AnchorSummary]:
    """If two time-separated sighting clusters imply superhuman velocity (> max_speed_mps),

    down-weight the older anchor's score.
    """
    if len(anchor_summaries) < 2:
        return anchor_summaries

    # Sort anchors by latest timestamp
    time_sorted = sorted(anchor_summaries, key=lambda a: a.latest_timestamp)
    updated = list(anchor_summaries)

    for i in range(len(time_sorted) - 1):
        older = time_sorted[i]
        newer = time_sorted[i + 1]

        dt = (newer.latest_timestamp - older.latest_timestamp).total_seconds()
        if dt > 1.0:  # Only evaluate if there's at least 1s time separation
            dist = math.hypot(newer.x - older.x, newer.y - older.y)
            speed = dist / dt
            if speed > max_speed_mps:
                # Down-weight older score
                penalty = max(0.2, max_speed_mps / speed)
                older.anchor_score *= penalty

    return updated


def check_simultaneous_conflict(
    top_candidate: ZoneScore,
    second_candidate: Optional[ZoneScore],
    adjacent_zone_ids: Set[int],
    top_anchor_time_s: float,
    second_anchor_time_s: float,
    time_window_s: float = 5.0,
    ratio_threshold: float = 0.6,
) -> bool:
    """Checks whether the top two zones are in simultaneous conflict:

    - non-adjacent
    - score of second >= 0.6 * top score
    - strongest sightings within time_window_s (5 s)
    """
    if not second_candidate:
        return False

    if second_candidate.zone_id in adjacent_zone_ids:
        return False  # Adjacent zones are not considered a conflicting anomaly

    if top_candidate.score <= 0:
        return False

    score_ratio = second_candidate.score / top_candidate.score
    if score_ratio < ratio_threshold:
        return False

    dt = abs(top_anchor_time_s - second_anchor_time_s)
    return dt <= time_window_s
