"""Split a chop book into the hole and the rest of the year."""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOLE_START = int(datetime(2026, 7, 16, tzinfo=timezone.utc).timestamp() * 1000)
HOLE_END = int(datetime(2026, 8, 15, tzinfo=timezone.utc).timestamp() * 1000)


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "exp-chop-push-1h"
    files = sorted((ROOT / "results" / name).glob("*/trades.csv"))
    if not files:
        raise SystemExit(f"no trades in {name}")
    rows = list(csv.DictReader(files[-1].open(encoding="utf-8")))
    hole = [r for r in rows if HOLE_START <= int(r["entry_time"]) < HOLE_END]
    rest = [r for r in rows if r not in hole]
    print(json.dumps({"file": str(files[-1]), "hole": _bucket(hole), "rest": _bucket(rest)}, indent=2))


def _bucket(rows):
    if not rows:
        return {"n": 0}
    return {
        "n": len(rows),
        "expectancy_r": round(sum(float(r["r_multiple"]) for r in rows) / len(rows), 4),
        "long": sum(r["side"] == "LONG" for r in rows),
        "short": sum(r["side"] == "SHORT" for r in rows),
        "stops": sum(r["exit_reason"] == "STOP" for r in rows),
        "targets": sum(r["exit_reason"] == "TARGET" for r in rows),
    }


if __name__ == "__main__":
    main()
