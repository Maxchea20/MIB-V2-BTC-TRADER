"""How far a losing Hunt trade went toward the target before the stop."""

import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars


def main():
    db = research_db_path(sys.argv[1] if len(sys.argv) > 1 else None)
    bars, info = load_bars(db, "BTC_USDT", None, None)
    print(f"{db.name} 1m={info.rows}")
    folders = [
        ROOT / "results" / "exp-hunt-desktop-cfi-v1",
        ROOT / "results" / "exp-hunt-desktop-cfi-swing",
    ]
    for folder in folders:
        files = sorted(folder.glob("*/trades.csv"))
        if not files:
            continue
        trades = list(csv.DictReader(files[-1].open(encoding="utf-8")))
        stops = [t for t in trades if t["exit_reason"] == "STOP"]
        print(json.dumps({"file": str(files[-1]), "stops": _reach(stops, bars)}, indent=2))


def _reach(trades, bars):
    reached = []
    for trade in trades:
        side = trade["side"]
        entry = float(trade["entry"])
        risk = abs(entry - float(trade["stop"]))
        start = int(trade["entry_time"])
        end = int(trade["exit_time"])
        lo, hi = 0, len(bars)
        while lo < hi:
            mid = (lo + hi) // 2
            if bars[mid].open_time < start:
                lo = mid + 1
            else:
                hi = mid
        favor = 0.0
        for bar in bars[lo:]:
            if bar.open_time > end:
                break
            favor = max(favor, bar.high - entry if side == "LONG" else entry - bar.low)
        reached.append(favor / risk)
    if not reached:
        return {"n": 0}
    reached.sort()
    def cut(x):
        return sum(v >= x for v in reached)
    return {
        "n": len(reached),
        "median_r": round(statistics.median(reached), 2),
        "reached_0.5r": cut(0.5),
        "reached_1.0r": cut(1.0),
        "reached_1.5r": cut(1.5),
        "reached_2.0r": cut(2.0),
    }


if __name__ == "__main__":
    main()
