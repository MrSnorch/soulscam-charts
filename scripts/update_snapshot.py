#!/usr/bin/env python3
"""
Fetch SteamDB's GetGraphMaxLoggedIn / GetGraphWeekLoggedIn APIs and update
docs/steamdb_snapshot.json. No cookies required (confirmed via HAR capture)
— just a normal User-Agent and Referer.

GetGraphMaxLoggedIn only covers the last ~8 days, not the game's all-time
peak, so peak_players_all_time accumulates: max(existing value in the file,
newest value from the API).
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

APPID = 4369490
SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "steamdb_snapshot.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Referer": f"https://steamdb.info/app/{APPID}/charts/",
    "Accept": "*/*",
}


def fetch(endpoint):
    url = f"https://steamdb.info/api/{endpoint}/?appid={APPID}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    if not data.get("success"):
        raise RuntimeError(f"{endpoint} returned success=false: {data}")
    return data["data"]


def main():
    try:
        max_data = fetch("GetGraphMaxLoggedIn")
        week_data = fetch("GetGraphWeekLoggedIn")
    except Exception as e:
        print(f"WARN: SteamDB fetch failed, leaving snapshot unchanged: {e}", file=sys.stderr)
        return

    window_peak = max(max_data["values"])

    hourly_values = [v for v in week_data["values"] if v is not None]
    peak_24h = max(hourly_values[-24:]) if hourly_values else None

    existing_peak_all_time = 0
    if os.path.exists(SNAPSHOT_PATH):
        with open(SNAPSHOT_PATH) as f:
            existing_peak_all_time = json.load(f).get("peak_players_all_time", 0)

    snapshot = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "peak_players_24h": peak_24h,
        "peak_players_all_time": max(existing_peak_all_time, window_peak),
    }

    with open(SNAPSHOT_PATH, "w") as f:
        json.dump(snapshot, f)

    print(f"Updated {SNAPSHOT_PATH}: {snapshot}")


if __name__ == "__main__":
    main()
