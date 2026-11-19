#!/usr/bin/env python3
"""Venue seeding script for KinBeacon Central Server."""

import argparse
import json
import sys
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description="Seed venue data into KinBeacon Central Server")
    parser.add_argument("--file", default="scripts/seed_demo.json", help="Path to venue seed JSON file")
    parser.add_argument("--server", default="http://localhost:8000", help="Central server base URL")
    parser.add_argument("--anchor-url", help="Override anchor base_url (e.g. http://192.168.1.50:5000)")
    args = parser.parse_args()

    try:
        with open(args.file, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading seed file '{args.file}': {e}", file=sys.stderr)
        sys.exit(1)

    if args.anchor_url:
        for a in data.get("anchors", []):
            a["base_url"] = args.anchor_url
            print(f"Overrode anchor {a.get('anchor_id')} URL -> {args.anchor_url}")

    url = f"{args.server.rstrip('/')}/api/v1/admin/seed"
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_body = resp.read().decode("utf-8")
            result = json.loads(resp_body)
            print("\n Venue seeded successfully:")
            print(f"  - Zones created: {result.get('zones_created')}")
            print(f"  - Anchors created: {result.get('anchors_created')} (Verified: {result.get('verified_anchors')})")
            print(f"  - Devices created: {result.get('devices_created')}")
            print(f"  - Adjacencies created: {result.get('adjacencies_created')}\n")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Failed to connect to central server at {url}: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
