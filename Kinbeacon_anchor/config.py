import os

# Anchor Identity
ANCHOR_ID = os.getenv("ANCHOR_ID", "ANCHOR-LAPTOP-01")

# Retention & Pruning
RETENTION_MINUTES = int(os.getenv("RETENTION_MINUTES", "15"))
PURGE_INTERVAL_SECONDS = int(os.getenv("PURGE_INTERVAL_SECONDS", "60"))

# Database Configuration
DB_PATH = os.getenv("DB_PATH", "ble_signals.db")

# BLE Scanner Configuration
DEVICE_PREFIX = os.getenv("DEVICE_PREFIX", "KINBEACON-")
BLE_RETRY_INTERVAL_SECONDS = int(os.getenv("BLE_RETRY_INTERVAL_SECONDS", "5"))

# API Server Configuration
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "5000"))
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
