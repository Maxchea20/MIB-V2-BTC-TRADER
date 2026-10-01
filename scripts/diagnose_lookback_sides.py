"""Side forensic for an existing trades.csv. Does not replay candles."""

import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


def num(row, key):
    return float(row[key])


def block(rows):
    if not rows:
        return {"n": 0}
    wins = [r for r in rows if num(r, "net_pnl") > 0]
    return {
        "n": len(rows),
        "win_rate": round(len(wins) / len(rows), 3),
        "expectancy_r": round(sum(num(r, "r_multiple") for r in rows) / len(rows), 3),
        "median_mfe_r": round(statistics.median(num(r, "mfe_r") for r in rows), 3),
        "median_mae_r": round(statistics.median(num(r, "mae_r") for r in rows), 3),
        "median_hold_min": round(statistics.median(num(r, "hold_seconds") for r in rows) / 60, 1),
        "median_stop_bps": round(statistics.median(abs(num(r, "entry") - num(r, "stop")) / num(r, "entry") * 10000 for r in rows), 1),
        "exits": dict(Counter(r["exit_reason"] for r in rows)),
        "events": dict(Counter(r["event"] for r in rows)),
    }


def main():
    root = Path("results/exp-hunt-lookback-20-v1")
    folders = sorted(p for p in root.glob("*") if (p / "trades.csv").exists())
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else folders[-1] / "trades.csv"
    rows = [r for r in csv.DictReader(path.open(encoding="utf-8")) if r["exit_reason"] != "END_OF_DATA"]
    out = {"file": str(path), "sides": {}}
    for side in ("LONG", "SHORT"):
        chosen = [r for r in rows if r["side"] == side]
        out["sides"][side] = block(chosen)
        out["sides"][side]["by_event"] = {
            event: block([r for r in chosen if r["event"] == event])
            for event in sorted(set(r["event"] for r in chosen))
        }
        months = defaultdict(list)
        for row in chosen:
            day = datetime.fromtimestamp(int(row["entry_time"]) / 1000, tz=timezone.utc).strftime("%Y-%m")
            months[day].append(row)
        out["sides"][side]["by_month"] = {month: block(items) for month, items in sorted(months.items())}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
