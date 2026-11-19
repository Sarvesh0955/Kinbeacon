"""
Live BLE diagnostic tool for KinBeacon.
Scans for BLE advertisements and inspects Manufacturer Data (Company ID 0xFFFF / 65535)
or advertised local names.
"""

import asyncio
import json
import re
import sys
from bleak import BleakScanner


def parse_device_id(raw_bytes: bytes, prefix: str = "kb-"):
    if not raw_bytes:
        return None
    raw_str = raw_bytes.decode("utf-8", errors="ignore").strip("\x00 \r\n")

    # JSON mode
    if "{" in raw_str:
        try:
            data = json.loads(raw_str)
            if isinstance(data, dict) and "device_id" in data:
                return data["device_id"], "JSON"
        except Exception:
            m = re.search(r'"device_id"\s*:\s*"([^"]+)"', raw_str)
            if m:
                return m.group(1), "Regex-JSON"

    # Compact KV mode
    m = re.search(rf"({re.escape(prefix)}[a-zA-Z0-9_\-]+)", raw_str)
    if m:
        return m.group(1), "Compact-KV"

    return None, "Unknown"


def detection_callback(device, adv_data):
    # Check if device has 0xFFFF (65535) manufacturer data
    mfg_dict = adv_data.manufacturer_data or {}
    has_target_mfg = (0xFFFF in mfg_dict) or (65535 in mfg_dict)

    name = adv_data.local_name or device.name or ""
    is_kb_name = name.startswith("kb-")

    if has_target_mfg or is_kb_name:
        print("\n" + "=" * 60)
        print(f"🎯 [MATCH] Device Address: {device.address}")
        print(f"   Local Name    : {name or '<None>'}")
        print(f"   RSSI          : {adv_data.rssi} dBm")

        if mfg_dict:
            for comp_id, raw_bytes in mfg_dict.items():
                print(f"   Company ID    : 0x{comp_id:04X} ({comp_id})")
                print(f"   Raw Bytes     : {raw_bytes}")
                print(f"   Hex Bytes     : {raw_bytes.hex()}")
                extracted_id, mode = parse_device_id(raw_bytes, prefix="kb-")
                if extracted_id:
                    print(f"   ✅ Extracted ID : '{extracted_id}' (Framing: {mode})")
                else:
                    print(f"   ⚠️ Could not extract 'kb-' device_id from payload")
        elif is_kb_name:
            print(f"   ✅ Extracted ID : '{name}' (Framing: BLE Local Name)")
        print("=" * 60)


async def main():
    print("==================================================")
    print("KinBeacon Live BLE Diagnostic Tool")
    print("Listening for BLE packets with Company ID 0xFFFF or 'kb-' prefix...")
    print("Press Ctrl+C to stop.")
    print("==================================================")

    async with BleakScanner(detection_callback=detection_callback):
        while True:
            await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDiagnostic scan stopped.")
