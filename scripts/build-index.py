#!/usr/bin/env python3
"""
Read every docs/hourly/*.json.gz snapshot and build:
- docs/recent.json: one row per hour with avg/max/min player_count (small,
  used by the hourly overview/compare charts).
- docs/points.json: raw {ts, player_count} points for the last RECENT_HOURS
  hours only, used by the live chart for an instant first paint.
- docs/points-by-day/YYYY-MM-DD.json.gz: full-resolution points for every
  day, one small gzip file each. The dashboard fetches these lazily when
  the person zooms/pans into a day not already in memory, so all history
  stays reachable without shipping it all up front.
- docs/points-index.json: which days have a points-by-day file and how
  many points each has, so the dashboard knows what it can fetch.
"""

import gzip
import json
import os
import glob
from datetime import datetime, timedelta, timezone

HOURLY_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "hourly")
BY_DAY_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "points-by-day")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "recent.json")
POINTS_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "points.json")
POINTS_INDEX_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "points-index.json")

RECENT_HOURS = 48  # how much raw history ships inline in points.json


def main():
    rows = []
    points_by_day = {}  # 'YYYY-MM-DD' -> list of {ts, player_count}
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

        day = data["hour"][:10]
        points_by_day.setdefault(day, []).extend(points)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(rows, f)

    os.makedirs(BY_DAY_DIR, exist_ok=True)
    index = []
    for day in sorted(points_by_day):
        pts = sorted(points_by_day[day], key=lambda p: p["ts"])
        day_path = os.path.join(BY_DAY_DIR, f"{day}.json.gz")
        with gzip.open(day_path, "wt") as f:
            json.dump(pts, f)
        index.append({"day": day, "count": len(pts)})

    with open(POINTS_INDEX_PATH, "w") as f:
        json.dump(index, f)

    # points.json: only the last RECENT_HOURS worth, for instant first paint
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RECENT_HOURS)
    all_points = sorted(
        (p for pts in points_by_day.values() for p in pts),
        key=lambda p: p["ts"],
    )
    recent_points = [p for p in all_points if datetime.fromisoformat(p["ts"]) >= cutoff]
    with open(POINTS_PATH, "w") as f:
        json.dump(recent_points, f)

    print(f"Wrote docs/recent.json: {len(rows)} hours")
    print(f"Wrote docs/points.json: {len(recent_points)} points (last {RECENT_HOURS}h)")
    print(f"Wrote docs/points-by-day/: {len(index)} day files, {sum(d['count'] for d in index)} points total")


if __name__ == "__main__":
    main()

