#!/usr/bin/env python3
"""Fetch High-impact USD macro events (Forex Factory) + manual BTC/ETH events,
and save them to events.json (no database). Keeps only the last 48h + upcoming."""

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

BASE = Path(__file__).parent
OUT_FILE = BASE / "events.json"
MANUAL_FILE = BASE / "manual_events.json"
FF_URLS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",  # may 404 early in the week
]
VALID_ASSETS = {"BTC", "ETH", "USD"}
HEADERS = {"User-Agent": "Mozilla/5.0 (crypto-events-bot; GitHub Actions)"}


def get_json(url, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 404:
                return []
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"[warn] {url} attempt {attempt + 1}/{retries}: {exc}")
            time.sleep(3 * (attempt + 1))
    return []


def to_utc(s):
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def row(title, asset, when, source):
    return {"title": title.strip(), "asset": asset, "impact": "High",
            "event_time": when.strftime("%Y-%m-%dT%H:%M:%SZ"), "source": source}


def fetch_macro():
    rows = []
    for url in FF_URLS:
        for ev in get_json(url):
            if ev.get("country") != "USD" or ev.get("impact") != "High":
                continue
            try:
                rows.append(row(ev["title"], "USD", to_utc(ev["date"]), "forexfactory"))
            except (KeyError, ValueError):
                continue
    return rows


def fetch_manual():
    if not MANUAL_FILE.exists():
        return []
    rows = []
    for ev in json.loads(MANUAL_FILE.read_text(encoding="utf-8")):
        try:
            asset = ev["asset"].upper()
            if asset not in VALID_ASSETS:
                raise ValueError(f"bad asset {asset}")
            rows.append(row(ev["title"], asset, to_utc(ev["event_time"]), "manual"))
        except (KeyError, ValueError) as exc:
            print(f"[warn] skipping manual event {ev}: {exc}")
    return rows


def load_existing():
    try:
        return json.loads(OUT_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return []


def main():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
    merged = {}
    for ev in load_existing() + fetch_macro() + fetch_manual():
        key = (ev["title"], ev["asset"], ev["event_time"])
        merged[key] = ev
    kept = [e for e in merged.values() if to_utc(e["event_time"]) >= cutoff]
    kept.sort(key=lambda e: e["event_time"])
    OUT_FILE.write_text(json.dumps(kept, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {len(kept)} high-impact events to events.json")


if __name__ == "__main__":
    main()
