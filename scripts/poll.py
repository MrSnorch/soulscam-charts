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
    delays = [0, 5, 15]  # immediate try, then two retries with backoff
    last_err = None
    for delay in delays:
        if delay:
            time.sleep(delay)
        try:
            with urllib.request.urlopen(API_URL, timeout=15) as resp:
                data = json.load(resp)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            print(f"WARN: request failed (retry in {delay or 'n/a'}s pattern): {e}", file=sys.stderr)
            continue

        result = data.get("response", {})
        if result.get("result") != 1:
            last_err = f"unexpected API result: {result}"
            print(f"WARN: {last_err}", file=sys.stderr)
            continue

        count = result.get("player_count")
        if count is None:
            last_err = "missing player_count in response"
            print(f"WARN: {last_err}", file=sys.stderr)
            continue

        return count

    print(f"ERROR: all retries exhausted, skipping this poll ({last_err})", file=sys.stderr)
    return None


def hour_key(dt):
    return dt.strftime("%Y-%m-%dT%H")


def flush_hour(hour, points, final=False):
    if not points:
        return
    os.makedirs(HOURLY_DIR, exist_ok=True)
    path = os.path.join(HOURLY_DIR, f"{hour}.json.gz")

    # Merge with existing file for this hour, if present (resumed run or
    # an earlier partial flush of the same hour).
    existing = []
    if os.path.exists(path):
        with gzip.open(path, "rt") as f:
            existing = json.load(f).get("points", [])

    merged = existing + points
    with gzip.open(path, "wt") as f:
        json.dump({"appid": APPID, "hour": hour, "points": merged}, f)

    tag = "final" if final else "partial"
    print(f"Flushed {len(points)} points ({tag}) -> docs/hourly/{hour}.json.gz ({len(merged)} total)", flush=True)


def main():
    print(f"Starting poll loop: interval={POLL_INTERVAL_SEC}s, run_duration={RUN_DURATION_SEC}s", flush=True)
    start = time.time()
    buffer = {}  # hour_key -> list of {ts, player_count} not yet flushed
    current_hour = None
    last_flush = start
    FLUSH_INTERVAL_SEC = 300  # write partial data every 5 min so it shows up quickly

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
            print(f"{now.isoformat()} player_count={count}", flush=True)

        if time.time() - last_flush >= FLUSH_INTERVAL_SEC:
            flush_hour(current_hour, buffer.get(current_hour, []))
            buffer[current_hour] = []
            last_flush = time.time()

        time.sleep(POLL_INTERVAL_SEC)

    # Flush whatever's left for the current (partial) hour before exiting.
    if current_hour is not None:
        flush_hour(current_hour, buffer.get(current_hour, []), final=True)


if __name__ == "__main__":
    main()
