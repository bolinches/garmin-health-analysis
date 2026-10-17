#!/usr/bin/env python3
"""
Fetch the Garmin Connect calendar: trips, races/events, naps, weigh-ins.

The Garmin calendar-service carries more than workouts. Luis adds trips and
races in the Garmin app, and this is where they land:

  jetLagTrip        one item PER DAY of a trip. This is the ONLY source for
                    FUTURE trips; get_stats().isJetLagDay only reports days
                    that have already happened.
  event             a race or booked event, WITH a title and usually a URL.
  wellnessActivity  Health Snapshot etc.
  nap               recorded naps.
  userTimeChanged   timezone change -- the tell for a flight day.
  weight            weigh-in day.
  bloodpressure     blood-pressure day.
  activity          recorded activities.

Endpoint: GET /calendar-service/year/{year}/month/{month-1}  (0-indexed month)
via the client's get_scheduled_workouts(year, month).

Outputs JSON to stdout for parsing by the agent.
"""

import json
import sys
import argparse
from datetime import date, datetime
from pathlib import Path

# Import auth helper
sys.path.insert(0, str(Path(__file__).parent))
from garmin_auth import get_client

try:
    from garminconnect import Garmin  # noqa: F401  (import-time dependency check)
except ImportError:
    print('{"error": "garminconnect not installed. Run: pip3 install garminconnect"}', file=sys.stderr)
    sys.exit(1)


def add_months(d, n):
    """Return the first day of the month n months from d."""
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, 1)


def month_start(d):
    return d.replace(day=1)


def _normalize(item):
    """Flatten one calendar item to a stable shape."""
    return {
        "date": item.get("date"),
        "item_type": item.get("itemType"),
        "title": item.get("title"),
        "url": item.get("url"),
        "activity_type_id": item.get("activityTypeId"),
        "duration_seconds": item.get("duration"),
        "distance_m": item.get("distance"),
        "calories": item.get("calories"),
        "weight_kg": item.get("weight"),
    }


def fetch_calendar(client, months_back=12, months_fwd=6):
    """Fetch every calendar item across a month window.

    Returns {"items": [...], "start": ..., "end": ..., "count": n}. A month that
    errors is reported in "errors" rather than aborting the whole window, because
    calendar-service has a history floor (months before ~2024-12 return nothing)
    and a single bad month should not hide the rest.
    """
    today = date.today()
    start = add_months(month_start(today), -months_back)
    end = add_months(month_start(today), months_fwd)

    items, errors = [], []
    seen = set()
    m = start
    while m <= end:
        try:
            r = client.get_scheduled_workouts(m.year, m.month) or {}
            for i in r.get("calendarItems") or []:
                if not (i.get("date") and i.get("itemType")):
                    continue
                # calendar-service re-yields some items across adjacent months
                # (an event near a month boundary arrives twice), so dedupe on the
                # natural key. Without this, `races` listed each event two or
                # more times.
                key = (i.get("date"), i.get("itemType"), i.get("title"), i.get("url"))
                if key in seen:
                    continue
                seen.add(key)
                items.append(_normalize(i))
        except Exception as e:
            errors.append(f"{m.year}-{m.month:02d}: {type(e).__name__}: {str(e)[:120]}")
        m = add_months(m, 1)

    items.sort(key=lambda x: (x["date"] or "", x["item_type"] or ""))
    out = {
        "items": items,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "count": len(items),
    }
    if errors:
        out["errors"] = errors
    return out


def _trips(client, months_back, months_fwd, with_names=False):
    """Trips only, one row per flagged day.

    Past days can be labelled from get_stats().jetLagTripName; future days
    cannot (the name is only published after the day has passed).
    """
    cal = fetch_calendar(client, months_back, months_fwd)
    today = date.today()
    days = sorted({i["date"] for i in cal["items"] if i["item_type"] == "jetLagTrip"})

    names = {}
    if with_names:
        for d in days:
            if d > today.isoformat():
                continue
            try:
                names[d] = (client.get_stats(d) or {}).get("jetLagTripName")
            except Exception:
                names[d] = None

    trips = [{"date": d, "is_future": d > today.isoformat(),
              "trip_name": names.get(d)} for d in days]

    # Group consecutive days into trip windows for a readable summary.
    windows = []
    for t in trips:
        if windows and (date.fromisoformat(t["date"]) - date.fromisoformat(windows[-1]["end"])).days == 1:
            windows[-1]["end"] = t["date"]
            windows[-1]["days"] += 1
            windows[-1]["trip_name"] = windows[-1]["trip_name"] or t["trip_name"]
        else:
            windows.append({"start": t["date"], "end": t["date"], "days": 1,
                            "trip_name": t["trip_name"]})

    out = {"trips": trips, "windows": windows, "count": len(trips),
           "start": cal["start"], "end": cal["end"]}
    if "errors" in cal:
        out["errors"] = cal["errors"]
    return out


def main():
    parser = argparse.ArgumentParser(description="Fetch the Garmin Connect calendar")
    parser.add_argument("metric", choices=["calendar", "trips", "races", "events", "nap", "summary"],
                        help="calendar=all items, trips=jetLagTrip days, races/events=event items, nap=naps, summary=counts by type")
    parser.add_argument("--months-back", type=int, default=12, help="Months of history to scan (default: 12)")
    parser.add_argument("--months-fwd", type=int, default=6, help="Months ahead to scan (default: 6)")
    parser.add_argument("--with-names", action="store_true",
                        help="For trips: also label past days with the trip name from get_stats (one call per past day)")
    args = parser.parse_args()

    client = get_client()
    if not client:
        print('{"error": "Not authenticated. Run: python3 scripts/garmin_auth.py login --email YOUR_EMAIL --password YOUR_PASSWORD"}')
        sys.exit(1)

    if args.metric == "trips":
        result = _trips(client, args.months_back, args.months_fwd, args.with_names)
    elif args.metric in ("races", "events"):
        cal = fetch_calendar(client, args.months_back, args.months_fwd)
        evs = [i for i in cal["items"] if i["item_type"] == "event"]
        result = {"events": evs, "count": len(evs), "start": cal["start"], "end": cal["end"]}
        if "errors" in cal:
            result["errors"] = cal["errors"]
    elif args.metric == "nap":
        cal = fetch_calendar(client, args.months_back, args.months_fwd)
        naps = [i for i in cal["items"] if i["item_type"] == "nap"]
        result = {"naps": naps, "count": len(naps), "start": cal["start"], "end": cal["end"]}
        if "errors" in cal:
            result["errors"] = cal["errors"]
    elif args.metric == "summary":
        cal = fetch_calendar(client, args.months_back, args.months_fwd)
        counts = {}
        for i in cal["items"]:
            counts[i["item_type"]] = counts.get(i["item_type"], 0) + 1
        trip_days = [i["date"] for i in cal["items"] if i["item_type"] == "jetLagTrip"]
        future = [d for d in trip_days if d > date.today().isoformat()]
        result = {"by_type": dict(sorted(counts.items(), key=lambda x: -x[1])),
                  "trip_days": len(trip_days), "future_trip_days": sorted(future),
                  "start": cal["start"], "end": cal["end"]}
        if "errors" in cal:
            result["errors"] = cal["errors"]
    else:
        result = fetch_calendar(client, args.months_back, args.months_fwd)

    print(json.dumps(result, indent=2))

    # An error dict is a failure, not data (same contract as garmin_data.py).
    if isinstance(result, dict) and result.get("error"):
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
