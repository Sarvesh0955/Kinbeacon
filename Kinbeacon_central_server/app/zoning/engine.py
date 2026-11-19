import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from app.core.config import Settings, settings as global_settings
from app.zoning.conflicts import check_simultaneous_conflict, check_speed_plausibility
from app.zoning.models import (
    AnchorMetadata,
    AnchorSummary,
    RawSighting,
    ZoneEstimateResult,
    ZoneMetadata,
    ZoneScore,
)
from app.zoning.scoring import summarize_anchor_sightings


class ZoneEngine:
    """Pure, side-effect free zone estimation engine."""

    def __init__(self, config: Optional[Settings] = None):
        self.cfg = config or global_settings

    def estimate(
        self,
        sightings: List[RawSighting],
        anchors: Dict[str, AnchorMetadata],
        zones: Dict[int, ZoneMetadata],
        now: Optional[datetime] = None,
    ) -> ZoneEstimateResult:
        if now is None:
            now = datetime.now(timezone.utc)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # Drop invalid sightings (out-of-bound RSSI or excessive future skew)
        valid_sightings: List[RawSighting] = []
        for s in sightings:
            if s.rssi < -120 or s.rssi > 0:
                continue
            s_time = s.observed_at if s.observed_at.tzinfo else s.observed_at.replace(tzinfo=timezone.utc)
            future_skew = (s_time - now).total_seconds()
            if future_skew > self.cfg.max_future_skew_s:
                continue
            # Also drop sightings older than analysis window (e.g. 15m or configured window)
            age = (now - s_time).total_seconds()
            if age > self.cfg.stale_max_s:
                continue
            valid_sightings.append(s)

        if not valid_sightings:
            return ZoneEstimateResult(
                winning_zone=None,
                confidence=0.0,
                confidence_label="LOW",
                estimated_position=None,
                last_seen_at=None,
                age_s=None,
                candidates=[],
                anchor_evidence=[],
                flags=["NOT_SEEN"],
                expanding_search_zone_ids=[],
            )

        # Group sightings by anchor
        by_anchor: Dict[str, List[RawSighting]] = {}
        for s in valid_sightings:
            by_anchor.setdefault(s.anchor_id, []).append(s)

        # Compute per-anchor summaries
        anchor_summaries: List[AnchorSummary] = []
        for anchor_id, s_list in by_anchor.items():
            meta = anchors.get(anchor_id)
            summary = summarize_anchor_sightings(
                anchor_id=anchor_id,
                sightings=s_list,
                anchor_meta=meta,
                now=now,
                tau=self.cfg.tau_decay_s,
                rssi_min=self.cfg.rssi_min,
                rssi_max=self.cfg.rssi_max,
            )
            if summary:
                anchor_summaries.append(summary)

        if not anchor_summaries:
            return ZoneEstimateResult(
                winning_zone=None,
                confidence=0.0,
                confidence_label="LOW",
                estimated_position=None,
                last_seen_at=None,
                age_s=None,
                candidates=[],
                anchor_evidence=[],
                flags=["NOT_SEEN"],
                expanding_search_zone_ids=[],
            )

        # Speed plausibility filter
        anchor_summaries = check_speed_plausibility(
            anchor_summaries,
            max_speed_mps=self.cfg.max_speed_mps,
        )

        # Group anchor summaries by zone
        by_zone: Dict[int, List[AnchorSummary]] = {}
        unassigned_anchors: List[AnchorSummary] = []
        for a in anchor_summaries:
            if a.zone_id is not None and a.zone_id in zones:
                by_zone.setdefault(a.zone_id, []).append(a)
            else:
                unassigned_anchors.append(a)

        # Compute zone score Z_z = sum of top-3 s_a
        zone_scores: List[ZoneScore] = []
        total_score_sum = 0.0

        for zone_id, a_list in by_zone.items():
            sorted_by_score = sorted(a_list, key=lambda x: x.anchor_score, reverse=True)
            top_3 = sorted_by_score[:3]
            z_score = sum(a.anchor_score for a in top_3)
            z_meta = zones[zone_id]
            zone_scores.append(
                ZoneScore(
                    zone_id=zone_id,
                    zone_name=z_meta.name,
                    score=z_score,
                    probability=0.0,
                    anchors_count=len(a_list),
                )
            )
            total_score_sum += z_score

        # Calculate probabilities
        for zs in zone_scores:
            zs.probability = (zs.score / total_score_sum) if total_score_sum > 0 else 0.0

        # Sort zones by score descending
        zone_scores.sort(key=lambda z: z.score, reverse=True)

        if not zone_scores or total_score_sum <= 0:
            return ZoneEstimateResult(
                winning_zone=None,
                confidence=0.0,
                confidence_label="LOW",
                estimated_position=None,
                last_seen_at=None,
                age_s=None,
                candidates=[],
                anchor_evidence=anchor_summaries,
                flags=["NOT_SEEN"],
                expanding_search_zone_ids=[],
            )

        top_zone_score = zone_scores[0]
        top_zone_meta = zones[top_zone_score.zone_id]
        top_zone_anchors = by_zone[top_zone_score.zone_id]

        # Overall latest sighting & age
        latest_timestamp = max(a.latest_timestamp for a in anchor_summaries)
        age_latest_s = max(0.0, (now - latest_timestamp).total_seconds())

        flags: List[str] = []

        # Stale check
        expanding_search_zones: List[int] = [top_zone_score.zone_id]
        if age_latest_s > self.cfg.stale_fresh_s:
            flags.append("STALE")
            # Expand search area to include adjacent zones
            expanding_search_zones.extend(sorted(top_zone_meta.adjacent_zone_ids))

        # Check conflicts
        k_conflict = 1.0
        second_candidate = zone_scores[1] if len(zone_scores) > 1 else None
        if second_candidate:
            top_a_time = max(a.latest_timestamp for a in top_zone_anchors).timestamp()
            second_a_anchors = by_zone[second_candidate.zone_id]
            second_a_time = max(a.latest_timestamp for a in second_a_anchors).timestamp()

            is_conflict = check_simultaneous_conflict(
                top_candidate=top_zone_score,
                second_candidate=second_candidate,
                adjacent_zone_ids=top_zone_meta.adjacent_zone_ids,
                top_anchor_time_s=top_a_time,
                second_anchor_time_s=second_a_time,
                time_window_s=self.cfg.simultaneous_conflict_time_window_s,
                ratio_threshold=self.cfg.simultaneous_conflict_ratio,
            )
            if is_conflict:
                flags.append("CONFLICT")
                k_conflict = 0.6

        # Single anchor check
        if len(top_zone_anchors) == 1:
            flags.append("SINGLE_ANCHOR")

        # Coverage factor C
        # Check unreachable anchors in top zone and its neighbours
        relevant_zone_ids = {top_zone_score.zone_id}.union(top_zone_meta.adjacent_zone_ids)
        total_relevant_anchors = 0
        unreachable_relevant_anchors = 0
        for a_meta in anchors.values():
            if a_meta.zone_id in relevant_zone_ids:
                total_relevant_anchors += 1
                if not a_meta.is_reachable:
                    unreachable_relevant_anchors += 1

        c_coverage = 1.0
        if total_relevant_anchors > 0 and unreachable_relevant_anchors > 0:
            unreachable_ratio = unreachable_relevant_anchors / total_relevant_anchors
            c_coverage = max(0.1, 1.0 - 0.5 * unreachable_ratio)
            flags.append("PARTIAL_COVERAGE")

        # Step 3: Confidence = D * F * E * C * K
        # Dominance D
        d_dominance = top_zone_score.probability if len(zone_scores) > 1 else 1.0

        # Freshness F
        f_freshness = math.exp(-age_latest_s / 60.0)

        # Evidence E: 0.5 * min(1, anchors_in_zone / 2) + 0.5 * q_best
        best_q = max(a.normalized_rssi for a in top_zone_anchors)
        anchors_in_zone_count = len(top_zone_anchors)
        e_evidence = 0.5 * min(1.0, anchors_in_zone_count / 2.0) + 0.5 * best_q

        confidence = max(0.0, min(1.0, d_dominance * f_freshness * e_evidence * c_coverage * k_conflict))

        if confidence >= 0.7:
            conf_label = "HIGH"
        elif confidence >= 0.4:
            conf_label = "MEDIUM"
        else:
            conf_label = "LOW"

        # Estimated position (weighted centroid of top zone anchors)
        pos_weight_sum = sum(a.anchor_score for a in top_zone_anchors)
        if pos_weight_sum > 0:
            est_x = sum(a.anchor_score * a.x for a in top_zone_anchors) / pos_weight_sum
            est_y = sum(a.anchor_score * a.y for a in top_zone_anchors) / pos_weight_sum
            est_floor = top_zone_anchors[0].floor
        else:
            est_x = top_zone_meta.centroid_x
            est_y = top_zone_meta.centroid_y
            est_floor = 0

        return ZoneEstimateResult(
            winning_zone=top_zone_meta,
            confidence=round(confidence, 4),
            confidence_label=conf_label,
            estimated_position={"x": round(est_x, 2), "y": round(est_y, 2), "floor": est_floor},
            last_seen_at=latest_timestamp,
            age_s=round(age_latest_s, 2),
            candidates=zone_scores,
            anchor_evidence=sorted(anchor_summaries, key=lambda a: a.anchor_score, reverse=True),
            flags=flags,
            expanding_search_zone_ids=expanding_search_zones,
        )
