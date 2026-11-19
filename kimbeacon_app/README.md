# KinBeacon Wearable / Mobile Advertiser App

A native Android mobile and wearable application built with **Kotlin** and **Jetpack Compose** (Material 3). It transforms an Android smartphone or wearable device into an active **KinBeacon** tracking transmitter, broadcasting cryptographic Rotating Proximity Identifiers (RPI) over Bluetooth Low Energy (BLE) to be captured by venue anchor nodes.

---

## Features

- **Continuous Foreground BLE Advertising:** Runs as an Android Foreground Service (`KinBeaconAdvertiserService`) with a wake lock, ensuring steady transmission even when the screen is locked or the app is minimized.
- **Multi-Framing Mode Engine:** Supports 3 configurable BLE advertisement payload framing formats using Bluetooth SIG Manufacturer Specific Data (Company ID `0xFFFF` / `65535`):
  1. **Compact KV (19 Bytes):** Raw string payload `kb-<16-hex-chars>` (e.g. `kb-21a7b9d22bbcb664`).
  2. **Extended Full JSON (32 Bytes):** JSON payload `{"device_id":"kb-<16-hex-chars>"}`.
  3. **Legacy JSON Base64 (27 Bytes):** JSON payload `{"device_id":"kb-<b64>"}`.
- **Cryptographic Ephemeral IDs (RPI):**
  - Elliptic Curve Diffie-Hellman (`ECDH` over `secp256r1`) key exchange.
  - AES-128 cryptographic token generation with 64-bit truncation.
  - Periodic ephemeral ID rotation to prevent third-party tracking.
- **Central Server Onboarding (`RegistrationClient`):**
  - Registers client public key via `POST /api/register`.
  - Performs network time synchronization to align token rotation windows with central server time.
  - Supports offline demo mode with locally persisted seed keys.
- **Live Diagnostics UI:**
  - Real-time display of active Device ID (`kb-...`).
  - Raw Bluetooth PDU byte sequence viewer.
  - Packet counter, execution time ($\mu\text{s}$), and BLE radio state indicators.

---

## Architecture Overview

```
 +───────────────────────────────────────────────────────────────────────────+
 |                              MainActivity UI                              |
 |              (Jetpack Compose Material 3 Diagnostic Dashboard)            |
 +─────────────────────────────────────┬─────────────────────────────────────+
                                       │ Starts / Stops
                                       v
 +───────────────────────────────────────────────────────────────────────────+
 |                        KinBeaconAdvertiserService                         |
 |                       (Android Foreground Service)                        |
 |                                                                           |
 |   +────────────────────────+                 +────────────────────────+   |
 |   |    CryptoKeyManager    |                 |  NrfBlePacketBuilder   |   |
 |   |  - ECDH (secp256r1)    | ── Generates ──>|  - Company ID: 0xFFFF  |   |
 |   |  - AES-128 Truncation  |      RPI Token  |  - Compact / JSON      |   |
 |   +────────────────────────+                 +───────────┬────────────+   |
 |                                                          │                |
 |                                                          v                |
 |                                              +────────────────────────+   |
 |                                              |  BluetoothLeAdvertiser |   |
 |                                              |  (2.4 GHz Radio PDU)   |   |
 |                                              +────────────────────────+   |
 +───────────────────────────────────────────────────────────────────────────+
                                       │
                                       │ BLE Broadcasts
                                       v
                     [KinBeacon Distributed Anchor Fleet]
```

---

## Technical Specifications

| Parameter | Value |
|---|---|
| **Language** | Kotlin 2.x |
| **UI Framework** | Jetpack Compose (BOM 2024.09+) |
| **Minimum SDK** | API Level 26 (Android 8.0 Oreo) |
| **Target SDK** | API Level 35 (Android 15) |
| **JDK Requirement**| JDK 11+ (JDK 17 recommended) |
| **Company ID** | `0xFFFF` (65535) |
| **Tx Power Level** | `ADVERTISE_TX_POWER_HIGH` |
| **Advertise Mode** | `ADVERTISE_MODE_LOW_LATENCY` |

---

## Android Permissions

The app declares and handles the necessary runtime permissions for BLE advertising and background operation:

- `BLUETOOTH_ADVERTISE` (Android 12+)
- `BLUETOOTH_CONNECT` (Android 12+)
- `ACCESS_FINE_LOCATION` / `ACCESS_COARSE_LOCATION`
- `FOREGROUND_SERVICE` & `FOREGROUND_SERVICE_CONNECTED_DEVICE` (Android 14+)
- `POST_NOTIFICATIONS` (Android 13+)
- `WAKE_LOCK`

---

## Building and Running

### 1. Using Android Studio
1. Open Android Studio (Hedgehog, Iguana, or later).
2. Select **Open** and choose the `kimbeacon_app` folder.
3. Allow Gradle to sync dependencies.
4. Connect a physical Android device with BLE Peripheral support enabled (BLE advertising is not supported on emulators).
5. Click **Run 'app'** (`Shift + F10`).

### 2. Using Gradle CLI

```bash
cd kimbeacon_app
# Build debug APK
./gradlew assembleDebug

# Install on connected device via ADB
./gradlew installDebug
```
The output APK will be located at:
`app/build/outputs/apk/debug/app-debug.apk`

---

## How It Interacts with KinBeacon System

1. **Broadcast Intake:** The app emits BLE packets containing Company ID `0xFFFF` and the identifier payload (e.g. `kb-21a7b9d22bbcb664`).
2. **Anchor Detection:** Laptops running `Kinbeacon_anchor` run Bleak continuous scanners that parse the `0xFFFF` manufacturer data, record the RSSI and timestamp, and insert the sighting into local SQLite databases.
3. **Localization:** When an operator triggers a search from `Kinbeacon_dashboard` or `Kinbeacon_central_server`, the central server pulls sightings from the anchors and calculates the device's zone and physical coordinates.
