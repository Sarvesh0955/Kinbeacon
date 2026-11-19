from datetime import datetime, timedelta, timezone
import pytest

from app.zoning.engine import ZoneEngine
from app.zoning.models import (
    AnchorMetadata,
    RawSighting,
    ZoneMetadata,
)


@pytest.fixture
def now():
    return datetime(2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_zones():
    return {
        1: ZoneMetadata(zone_id=1, name="Zone 1", centroid_x=10, centroid_y=10, adjacent_zone_ids={2}),
        2: ZoneMetadata(zone_id=2, name="Zone 2", centroid_x=30, centroid_y=10, adjacent_zone_ids={1, 3}),
        3: ZoneMetadata(zone_id=3, name="Zone 3", centroid_x=60, centroid_y=10, adjacent_zone_ids={2}),
    }


@pytest.fixture
def sample_anchors():
    return {
        "A1": AnchorMetadata(anchor_id="A1", zone_id=1, x=10, y=10, is_reachable=True),
        "A2": AnchorMetadata(anchor_id="A2", zone_id=1, x=12, y=12, is_reachable=True),
        "B1": AnchorMetadata(anchor_id="B1", zone_id=2, x=30, y=10, is_reachable=True),
        "C1": AnchorMetadata(anchor_id="C1", zone_id=3, x=60, y=10, is_reachable=True),
    }


def test_no_sightings(now, sample_zones, sample_anchors):
    engine = ZoneEngine()
    result = engine.estimate([], sample_anchors, sample_zones, now=now)
    assert result.winning_zone is None
    assert result.confidence == 0.0
    assert "NOT_SEEN" in result.flags


def test_clear_single_zone(now, sample_zones, sample_anchors):
    engine = ZoneEngine()
    # Sightings at A1 and A2, both recent and strong (-50 dBm)
    sightings = [
        RawSighting("A1", now - timedelta(seconds=2), -50),
        RawSighting("A1", now - timedelta(seconds=1), -48),
        RawSighting("A1", now, -52),
        RawSighting("A2", now - timedelta(seconds=1), -55),
        RawSighting("A2", now, -54),
    ]
    result = engine.estimate(sightings, sample_anchors, sample_zones, now=now)
    assert result.winning_zone is not None
    assert result.winning_zone.zone_id == 1
    assert result.confidence_label == "HIGH"
    assert "SINGLE_ANCHOR" not in result.flags
    assert "STALE" not in result.flags
    assert len(result.candidates) == 1
    assert result.candidates[0].probability == 1.0


def test_single_anchor_flag(now, sample_zones, sample_anchors):
    engine = ZoneEngine()
    sightings = [
        RawSighting("A1", now - timedelta(seconds=1), -55),
        RawSighting("A1", now, -55),
    ]
    result = engine.estimate(sightings, sample_anchors, sample_zones, now=now)
    assert result.winning_zone.zone_id == 1
    assert "SINGLE_ANCHOR" in result.flags
    # With a single anchor, evidence E <= 0.75, so confidence cannot be 1.0
    assert result.confidence < 0.8


def test_stale_sightings(now, sample_zones, sample_anchors):
    engine = ZoneEngine()
    # Sightings from 2 minutes ago (120 s > 30 s stale threshold)
    sightings = [
        RawSighting("A1", now - timedelta(seconds=125), -55),
        RawSighting("A1", now - timedelta(seconds=120), -52),
    ]
    result = engine.estimate(sightings, sample_anchors, sample_zones, now=now)
    assert result.winning_zone.zone_id == 1
    assert "STALE" in result.flags
    assert 2 in result.expanding_search_zone_ids  # Zone 2 is adjacent to Zone 1
    assert result.confidence < 0.4  # F decayed heavily


def test_simultaneous_conflict(now, sample_zones, sample_anchors):
    engine = ZoneEngine()
    # Zone 1 (A1) and Zone 3 (C1) are non-adjacent.
    # Strong simultaneous sightings in both.
    sightings = [
        RawSighting("A1", now - timedelta(seconds=1), -50),
        RawSighting("A1", now, -50),
        RawSighting("C1", now - timedelta(seconds=1), -52),
        RawSighting("C1", now, -51),
    ]
    result = engine.estimate(sightings, sample_anchors, sample_zones, now=now)
    assert "CONFLICT" in result.flags
    assert len(result.candidates) >= 2


def test_partial_coverage_penalty(now, sample_zones, sample_anchors):
    engine = ZoneEngine()
    # Make A2 unreachable in Zone 1
    sample_anchors["A2"].is_reachable = False
    sightings = [
        RawSighting("A1", now - timedelta(seconds=1), -50),
        RawSighting("A1", now, -50),
    ]
    result = engine.estimate(sightings, sample_anchors, sample_zones, now=now)
    assert "PARTIAL_COVERAGE" in result.flags


def test_probabilities_sum_to_one(now, sample_zones, sample_anchors):
    engine = ZoneEngine()
    sightings = [
        RawSighting("A1", now, -60),
        RawSighting("B1", now, -65),
        RawSighting("C1", now, -70),
    ]
    result = engine.estimate(sightings, sample_anchors, sample_zones, now=now)
    prob_sum = sum(c.probability for c in result.candidates)
    assert pytest.approx(prob_sum, 0.001) == 1.0
