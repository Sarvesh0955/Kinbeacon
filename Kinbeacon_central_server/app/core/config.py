from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Central server settings."""

    # Server config
    app_name: str = "KinBeacon Central Server"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "sqlite+aiosqlite:///./kinbeacon.db"

    # Network & Transport
    per_anchor_connect_timeout_s: float = 0.5
    per_anchor_read_timeout_s: float = 2.0
    global_search_deadline_s: float = 5.0
    max_anchor_concurrency: int = 200
    max_payload_bytes: int = 2 * 1024 * 1024  # 2 MB response cap

    # Time Skew & Retention
    max_future_skew_s: float = 5.0
    analysis_window_s: float = 300.0  # 5 minutes
    max_raw_sightings_persisted_per_anchor: int = 50
    retention_ttl_s: float = 900.0  # 15 minutes TTL for historical sightings

    # Health & Circuit Breaker
    circuit_breaker_failures: int = 3
    circuit_breaker_cooldown_s: float = 30.0
    health_probe_interval_s: float = 15.0

    # Zone Algorithm Tuning
    tau_decay_s: float = 20.0
    rssi_min: float = -100.0
    rssi_max: float = -40.0
    stale_fresh_s: float = 30.0
    stale_max_s: float = 600.0  # 10 minutes
    max_speed_mps: float = 2.5
    simultaneous_conflict_time_window_s: float = 5.0
    simultaneous_conflict_ratio: float = 0.6  # scores within 60%

    # Security & Auth (Optional / Phase 6 hardening)
    api_key: str | None = None  # If set, validates X-API-Key header on server endpoints
    anchor_api_key: str | None = None  # If set, sends X-Anchor-Key to anchors

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
