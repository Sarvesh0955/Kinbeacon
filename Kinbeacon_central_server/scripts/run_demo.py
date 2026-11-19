#!/usr/bin/env python3
"""Run demo search against KinBeacon Central Server."""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description="Run KinBeacon device search demo")
    parser.add_argument("--device", default="kb-phone1", help="Device ID to search for")
    parser.add_argument("--server", default="http://localhost:8000", help="Central server base URL")
    args = parser.parse_args()

    url = f"{args.server.rstrip('/')}/api/v1/searches"
    payload = json.dumps({"device_id": args.device}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            data = json.loads(resp.read().decode("utf-8"))

            print("\n================ KinBeacon Search Result ================")
            print(f" Search ID:       {data.get('search_id')}")
            print(f" Device ID:       {data.get('device_id')}")
            print(f" Status:          {data.get('status')}")
            zone = data.get("zone")
            zone_str = f"{zone.get('name')} (ID: {zone.get('id')})" if zone else "None (Device not located)"
            print(f" Winning Zone:    {zone_str}")
            print(f" Confidence:      {data.get('confidence')} [{data.get('confidence_label')}]")
            pos = data.get("estimated_position")
            if pos:
                print(f" Estimated Pos:   x={pos.get('x')}m, y={pos.get('y')}m, floor={pos.get('floor')}")
            print(f" Age:             {data.get('age_s')}s")
            print(f" Flags:           {', '.join(data.get('flags', [])) or 'None'}")

            print("\n Fleet Summary:")
            anchors = data.get("anchors", {})
            print(f"  Targeted: {anchors.get('targeted')}, Responded: {anchors.get('responded')}, "
                  f"Timed Out: {anchors.get('timed_out')}, Failed: {anchors.get('failed')}")
            if anchors.get("unreachable"):
                print(f"  Unreachable anchors: {', '.join(anchors.get('unreachable'))}")

            print("\n Anchor Evidence:")
            for ev in data.get("evidence", []):
                print(f"  * Anchor {ev.get('anchor_id')}: {ev.get('samples_count')} samples, "
                      f"RSSI={ev.get('smoothed_rssi')} dBm, Score={ev.get('anchor_score')}, Age={ev.get('age_s')}s")

            print(f"\n Roundtrip API Latency: {elapsed_ms:.2f} ms")
            print("=========================================================\n")

    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Failed to query central server at {url}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
