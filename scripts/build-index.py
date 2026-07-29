#!/usr/bin/env python3
"""
Read every docs/hourly/*.json.gz snapshot and build two files:
- docs/recent.json: one row per hour with avg/max player_count (small,
  used by the hourly overview/compare charts).
- docs/points.json: every raw {ts, player_count} point across all hours,
  used by the live 5-minute-resolution chart.
"""

import gzip
import json
import os
import glob

HOURLY_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "hourly")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "recent.json")
POINTS_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "points.json")


def main():
    rows = []
    all_points = []
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
        all_points.extend(points)

    all_points.sort(key=lambda p: p["ts"])

    with open(OUTPUT_PATH, "w") as f:
        json.dump(rows, f)
    with open(POINTS_PATH, "w") as f:
        json.dump(all_points, f)

    print(f"Wrote docs/recent.json: {len(rows)} hours")
    print(f"Wrote docs/points.json: {len(all_points)} points")


if __name__ == "__main__":
    main()
