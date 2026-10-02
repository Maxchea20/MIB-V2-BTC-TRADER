"""Side and month split for the latest chop result."""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "exp-chop-push-1h"
    files = sorted((ROOT / "results" / name).glob("*/trades.csv"))
    if not files:
        raise SystemExit(f"no trades in {name}")
    rows = list(csv.DictReader(files[-1].open(encoding="utf-8")))
    print(json.dumps({"file": str(files[-1]), "sides": _sides(rows), "months": _months(rows)}, indent=2))


def _sides(rows):
    out = {}
    for side in ("LONG", "SHORT"):
        got = [r for r in rows if r["side"] == side]
        out[side] = _bucket(got)
    return out


def _months(rows):
    out = {}
    for row in rows:
        key = datetime.fromtimestamp(int(row["entry_time"]) / 1000, timezone.utc).strftime("%Y-%m")
        out.setdefault(key, []).append(row)
    return {key: _bucket(out[key]) for key in sorted(out)}


def _bucket(rows):
    if not rows:
        return {"n": 0}
    return {
        "n": len(rows),
        "expectancy_r": round(sum(float(r["r_multiple"]) for r in rows) / len(rows), 4),
        "stops": sum(r["exit_reason"] == "STOP" for r in rows),
        "targets": sum(r["exit_reason"] == "TARGET" for r in rows),
    }


if __name__ == "__main__":
    main()
