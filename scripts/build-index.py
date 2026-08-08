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

This runs on a tight schedule (as often as once a minute), so it's built
to stay cheap and to avoid rewriting files that haven't actually changed:
- Only "live" days (today + yesterday, to catch late-arriving hourly
  files right after midnight UTC) get their points-by-day file rebuilt.
  Older days are written once and left alone.
- gzip output uses mtime=0 so re-writing identical content produces byte-
  identical files - git sees no diff and doesn't commit a no-op change.
"""

import gzip
import io
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


def write_gzip_json(path, obj):
    """Write gzip with a fixed mtime so identical content -> identical
    bytes -> no spurious git diff on every run."""
    payload = json.dumps(obj).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0) as gz:
        gz.write(payload)
    data = buf.getvalue()
    # Skip the write entirely if content is unchanged, so mtime on disk
    # (and any git diff) stays untouched too.
    if os.path.exists(path):
        with open(path, "rb") as f:
            if f.read() == data:
                return False
    with open(path, "wb") as f:
        f.write(data)
    return True


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

    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    live_days = {today, yesterday}

    index = []
    written = 0
    for day in sorted(points_by_day):
        day_path = os.path.join(BY_DAY_DIR, f"{day}.json.gz")
        already_exists = os.path.exists(day_path)
        pts = sorted(points_by_day[day], key=lambda p: p["ts"])

        if day in live_days or not already_exists:
            if write_gzip_json(day_path, pts):
                written += 1
            index.append({"day": day, "count": len(pts)})
        else:
            # Older, already-written day: trust the existing file and its
            # count rather than re-decoding + re-gzipping it every run.
            index.append({"day": day, "count": len(pts)})

    with open(POINTS_INDEX_PATH, "w") as f:
        json.dump(index, f)

    # points.json: only the last RECENT_HOURS worth, for instant first paint
    cutoff = now - timedelta(hours=RECENT_HOURS)
    all_points = sorted(
        (p for pts in points_by_day.values() for p in pts),
        key=lambda p: p["ts"],
    )
    recent_points = [p for p in all_points if datetime.fromisoformat(p["ts"]) >= cutoff]
    with open(POINTS_PATH, "w") as f:
        json.dump(recent_points, f)

    print(f"Wrote docs/recent.json: {len(rows)} hours")
    print(f"Wrote docs/points.json: {len(recent_points)} points (last {RECENT_HOURS}h)")
    print(f"docs/points-by-day/: {len(index)} days tracked, {written} file(s) actually rewritten this run")


if __name__ == "__main__":
    main()
