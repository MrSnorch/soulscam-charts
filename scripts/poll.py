#!/usr/bin/env python3
"""
Poll Steam's GetNumberOfCurrentPlayers every 60s for one run (~5.5h, staying
under GitHub Actions' 6h job limit), buffer points in memory, and flush one
gzip JSON file per UTC hour into docs/hourly/. The workflow commits after
each flush and re-triggers itself when the run ends.
"""

import gzip
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

APPID = 4369490
API_URL = f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={APPID}"
POLL_INTERVAL_SEC = 60
RUN_DURATION_SEC = int(os.environ.get("RUN_DURATION_SEC", 5.5 * 3600))
HOURLY_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "hourly")


def fetch_player_count():
    try:
        with urllib.request.urlopen(API_URL, timeout=15) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"WARN: request failed: {e}", file=sys.stderr)
        return None

    result = data.get("response", {})
    if result.get("result") != 1:
        print(f"WARN: unexpected API result: {result}", file=sys.stderr)
        return None
    return result.get("player_count")


def hour_key(dt):
    return dt.strftime("%Y-%m-%dT%H")


def flush_hour(hour, points):
    if not points:
        return
    os.makedirs(HOURLY_DIR, exist_ok=True)
    path = os.path.join(HOURLY_DIR, f"{hour}.json.gz")

    # Merge with existing file for this hour, if present (e.g. resumed run).
    existing = []
    if os.path.exists(path):
        with gzip.open(path, "rt") as f:
            existing = json.load(f).get("points", [])

    merged = existing + points
    with gzip.open(path, "wt") as f:
        json.dump({"appid": APPID, "hour": hour, "points": merged}, f)

    print(f"Flushed {len(points)} points -> docs/hourly/{hour}.json.gz ({len(merged)} total)")


def main():
    start = time.time()
    buffer = {}  # hour_key -> list of {ts, player_count}
    current_hour = None

    while time.time() - start < RUN_DURATION_SEC:
        now = datetime.now(timezone.utc)
        hk = hour_key(now)

        if current_hour is not None and hk != current_hour:
            flush_hour(current_hour, buffer.get(current_hour, []))
            buffer.pop(current_hour, None)
        current_hour = hk

        count = fetch_player_count()
        if count is not None:
            buffer.setdefault(hk, []).append({
                "ts": now.isoformat(),
                "player_count": count,
            })
            print(f"{now.isoformat()} player_count={count}")

        time.sleep(POLL_INTERVAL_SEC)

    # Flush whatever's left for the current (partial) hour before exiting.
    if current_hour is not None:
        flush_hour(current_hour, buffer.get(current_hour, []))


if __name__ == "__main__":
    main()
