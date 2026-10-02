"""Path from entry to stop or target for the desktop Hunt files."""

import csv
import json
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
        row = {"file": str(files[-1]), "combined": _path(trades, bars)}
        row["long"] = _path([t for t in trades if t["side"] == "LONG"], bars)
        row["short"] = _path([t for t in trades if t["side"] == "SHORT"], bars)
        print(json.dumps(row, indent=2))
    if not any(folder.glob("*/trades.csv") for folder in folders):
        raise SystemExit("no Hunt trades.csv")


def _path(trades, bars):
    out = {"n": len(trades), "target_straight": 0, "target_after_going_against": 0, "stop_straight": 0, "stop_after_going_in_favor": 0}
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
        against = favor = 0.0
        for bar in bars[lo:]:
            if bar.open_time > end:
                break
            if side == "LONG":
                against = max(against, entry - bar.low)
                favor = max(favor, bar.high - entry)
            else:
                against = max(against, bar.high - entry)
                favor = max(favor, entry - bar.low)
        hit_target = trade["exit_reason"] == "TARGET"
        if hit_target and against < 0.5 * risk:
            out["target_straight"] += 1
        elif hit_target:
            out["target_after_going_against"] += 1
        elif favor < 0.5 * risk:
            out["stop_straight"] += 1
        else:
            out["stop_after_going_in_favor"] += 1
    return out


if __name__ == "__main__":
    main()
