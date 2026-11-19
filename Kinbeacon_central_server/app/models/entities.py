from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class Zone(Base):
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    centroid_x = Column(Float, default=0.0, nullable=False)
    centroid_y = Column(Float, default=0.0, nullable=False)
    metadata_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    anchors = relationship("Anchor", back_populates="zone", lazy="selectin")


class ZoneAdjacency(Base):
    __tablename__ = "zone_adjacency"

    id = Column(Integer, primary_key=True)
    zone_a_id = Column(Integer, ForeignKey("zones.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_b_id = Column(Integer, ForeignKey("zones.id", ondelete="CASCADE"), nullable=False, index=True)

    __table_args__ = (
        Index("ix_zone_adjacency_pair", "zone_a_id", "zone_b_id", unique=True),
    )


class Anchor(Base):
    __tablename__ = "anchors"

    id = Column(Integer, primary_key=True, index=True)
    anchor_id = Column(String(64), unique=True, index=True, nullable=False)
    zone_id = Column(Integer, ForeignKey("zones.id", ondelete="SET NULL"), nullable=True, index=True)
    x = Column(Float, default=0.0, nullable=False)
    y = Column(Float, default=0.0, nullable=False)
    floor = Column(Integer, default=0, nullable=False)
    base_url = Column(String(255), nullable=False)

    enabled = Column(Boolean, default=True, nullable=False)
    verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    verify_note = Column(String(255), nullable=True)

    health_state = Column(String(20), default="UNKNOWN", nullable=False)  # UP, DEGRADED, DOWN, UNKNOWN
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    consecutive_failures = Column(Integer, default=0, nullable=False)
    circuit_open_until = Column(DateTime(timezone=True), nullable=True)
    clock_offset_ms = Column(Float, default=0.0, nullable=False)
    metadata_json = Column(JSON, default=dict, nullable=False)

    zone = relationship("Zone", back_populates="anchors", lazy="selectin")

    @property
    def is_active(self) -> bool:
        if not self.enabled:
            return False
        if self.circuit_open_until:
            now = utcnow()
            # If circuit_open_until is naive, make it aware
            circuit_open = self.circuit_open_until
            if circuit_open.tzinfo is None:
                circuit_open = circuit_open.replace(tzinfo=timezone.utc)
            if circuit_open > now:
                return False
        return True


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(64), unique=True, index=True, nullable=False)
    display_name = Column(String(100), nullable=True)
    guardian_ref = Column(String(100), nullable=True)
    status = Column(String(20), default="ACTIVE", nullable=False)  # ACTIVE, INACTIVE
    metadata_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class Search(Base):
    __tablename__ = "searches"

    id = Column(String(36), primary_key=True)  # UUID string
    device_id = Column(String(64), nullable=False, index=True)
    requested_by = Column(String(100), nullable=True)
    status = Column(String(20), default="RUNNING", nullable=False)  # RUNNING, COMPLETED, PARTIAL, FAILED
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    anchors_targeted = Column(Integer, default=0, nullable=False)
    anchors_responded = Column(Integer, default=0, nullable=False)

    results = relationship("SearchAnchorResult", back_populates="search", lazy="selectin", cascade="all, delete-orphan")
    sightings = relationship("Sighting", back_populates="search", lazy="selectin", cascade="all, delete-orphan")
    estimates = relationship("ZoneEstimate", back_populates="search", lazy="selectin", cascade="all, delete-orphan")


class SearchAnchorResult(Base):
    __tablename__ = "search_anchor_results"

    id = Column(Integer, primary_key=True)
    search_id = Column(String(36), ForeignKey("searches.id", ondelete="CASCADE"), nullable=False, index=True)
    anchor_id = Column(String(64), nullable=False, index=True)
    outcome = Column(String(20), nullable=False)  # OK, EMPTY, TIMEOUT, ERROR, SKIPPED
    http_status = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    sightings_count = Column(Integer, default=0, nullable=False)
    dropped_count = Column(Integer, default=0, nullable=False)
    error = Column(Text, nullable=True)

    search = relationship("Search", back_populates="results")


class Sighting(Base):
    __tablename__ = "sightings"

    id = Column(Integer, primary_key=True)
    search_id = Column(String(36), ForeignKey("searches.id", ondelete="CASCADE"), nullable=False, index=True)
    anchor_id = Column(String(64), nullable=False, index=True)
    device_id = Column(String(64), nullable=False, index=True)
    observed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    rssi = Column(Integer, nullable=False)

    search = relationship("Search", back_populates="sightings")

    __table_args__ = (
        Index("ix_sightings_search_observed", "search_id", "observed_at"),
        Index("ix_sightings_dedupe", "anchor_id", "device_id", "observed_at"),
    )


class ZoneEstimate(Base):
    __tablename__ = "zone_estimates"

    id = Column(Integer, primary_key=True)
    search_id = Column(String(36), ForeignKey("searches.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id", ondelete="SET NULL"), nullable=True, index=True)
    rank = Column(Integer, default=1, nullable=False)
    score = Column(Float, default=0.0, nullable=False)
    probability = Column(Float, default=0.0, nullable=False)
    confidence = Column(Float, default=0.0, nullable=False)
    flags = Column(JSON, default=list, nullable=False)
    evidence = Column(JSON, default=dict, nullable=False)

    search = relationship("Search", back_populates="estimates")
