"""Where the chop entry sat between the low and the high."""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "exp-chop-push-1h"
    files = sorted((ROOT / "results" / name).glob("*/trades.csv"))
    if not files:
        raise SystemExit(f"no trades in {name}")
    rows = list(csv.DictReader(files[-1].open(encoding="utf-8")))
    places = [_place(r) for r in rows]
    places = [p for p in places if p is not None]
    print(json.dumps({
        "file": str(files[-1]),
        "n": len(places),
        "median_position": _median(places),
        "bottom_quarter": round(sum(p <= 0.25 for p in places) / len(places), 4) if places else 0,
        "middle": round(sum(0.25 < p < 0.75 for p in places) / len(places), 4) if places else 0,
        "top_quarter": round(sum(p >= 0.75 for p in places) / len(places), 4) if places else 0,
        "long_median": _median([_place(r) for r in rows if r["side"] == "LONG"]),
        "short_median": _median([_place(r) for r in rows if r["side"] == "SHORT"]),
    }, indent=2))


def _place(row):
    entry = float(row["entry"])
    stop = float(row["stop"])
    target = float(row["target"])
    if row["side"] == "LONG":
        span = (target - stop) * 2
        if span <= 0:
            return None
        return (entry - stop) / span
    span = (stop - target) * 2
    if span <= 0:
        return None
    return (stop - entry) / span


def _median(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return None
    return round(values[len(values) // 2], 4)


if __name__ == "__main__":
    main()
