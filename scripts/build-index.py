#!/usr/bin/env python3
"""
Read every docs/hourly/*.json.gz snapshot and build docs/recent.json: one
row per hour with avg/max player_count. This keeps the dashboard's payload
small (no need to fetch dozens of gzip files in the browser).
"""

import gzip
import json
import os
import glob

HOURLY_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "hourly")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "recent.json")


def main():
    rows = []
    for path in sorted(glob.glob(os.path.join(HOURLY_DIR, "*.json.gz"))):
        with gzip.open(path, "rt") as f:
            data = json.load(f)

        points = data.get("points", [])
        if not points:
            continue

        counts = [p["player_count"] for p in points]
        rows.append({
            "hour": data["hour"],
            "avg": round(sum(counts) / len(counts)),
            "max": max(counts),
            "min": min(counts),
        })

    with open(OUTPUT_PATH, "w") as f:
        json.dump(rows, f)

    print(f"Wrote docs/recent.json: {len(rows)} hours")


if __name__ == "__main__":
    main()
