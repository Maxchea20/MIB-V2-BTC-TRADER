"""Count the failed-push box on the research year. No orders."""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.market_structure.failed_push_range import detect_push_range

HOLE_START = int(datetime(2026, 7, 16, tzinfo=timezone.utc).timestamp() * 1000)
HOLE_END = int(datetime(2026, 8, 15, tzinfo=timezone.utc).timestamp() * 1000)


def main():
    db = research_db_path(sys.argv[1] if len(sys.argv) > 1 else None)
    files = sorted((ROOT / "results" / "exp-hunt-desktop-cfi-v1").glob("*/trades.csv"))
    trades = list(csv.DictReader(files[-1].open(encoding="utf-8"))) if files else []
    bars, info = load_bars(db, "BTC_USDT", None, None)
    print(f"{db.name} 1m={info.rows}")
    rows = []
    for name, span, lookback in (("1h", "1h", 240), ("4h", "4h", 180)):
        series = resample(bars, span)
        active = _flags(series, lookback)
        hole = [t for t in trades if HOLE_START <= int(t["entry_time"]) < HOLE_END]
        rows.append({
            "clock": name,
            "active_share": round(sum(active.values()) / len(active), 4) if active else 0,
            "hunt_inside": _count(trades, active),
            "hole_n": len(hole),
            "hole_inside": _count(hole, active),
        })
    print(json.dumps({"rows": rows}, indent=2))


def _flags(series, lookback):
    out = {}
    for i in range(lookback, len(series)):
        state = detect_push_range(series[i - lookback + 1 : i + 1])
        out[series[i].open_time] = state.active and state.phase == "RANGE"
    return out


def _count(trades, active):
    keys = sorted(active)
    n = 0
    for trade in trades:
        ts = int(trade["entry_time"])
        lo, hi = 0, len(keys)
        while lo < hi:
            mid = (lo + hi) // 2
            if keys[mid] <= ts:
                lo = mid + 1
            else:
                hi = mid
        if lo and active[keys[lo - 1]]:
            n += 1
    return n


if __name__ == "__main__":
    main()
