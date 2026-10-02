"""How many full Hunt trades sat in a 30-bar 4h range. No orders."""

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
from btc_research.market_structure.range_detector import RangeParams, detect_range

HOLE_START = int(datetime(2026, 7, 16, tzinfo=timezone.utc).timestamp() * 1000)
HOLE_END = int(datetime(2026, 8, 15, tzinfo=timezone.utc).timestamp() * 1000)


def main():
    db = research_db_path(sys.argv[1] if len(sys.argv) > 1 else None)
    files = sorted((ROOT / "results" / "exp-hunt-desktop-cfi-v1").glob("*/trades.csv"))
    if not files:
        raise SystemExit("no full Hunt trades")
    trades = list(csv.DictReader(files[-1].open(encoding="utf-8")))
    bars, _info = load_bars(db, "BTC_USDT", None, None)
    bars_4h = resample(bars, "4h")
    params = RangeParams(lookback=30)
    active_at = {}
    for i in range(30, len(bars_4h)):
        state = detect_range(bars_4h[i - 29 : i + 1], None, params)
        active_at[bars_4h[i].open_time] = state.score >= 85
    keys = sorted(active_at)
    inside = [t for t in trades if _inside(int(t["entry_time"]), keys, active_at)]
    hole = [t for t in trades if HOLE_START <= int(t["entry_time"]) < HOLE_END]
    hole_inside = [t for t in hole if _inside(int(t["entry_time"]), keys, active_at)]
    print(json.dumps({
        "file": str(files[-1]),
        "hunt": _bucket(trades),
        "hunt_inside_4h_85": _bucket(inside),
        "hole_16jul_14aug": _bucket(hole),
        "hole_inside_4h_85": _bucket(hole_inside),
    }, indent=2))


def _inside(ts, keys, active_at):
    lo, hi = 0, len(keys)
    while lo < hi:
        mid = (lo + hi) // 2
        if keys[mid] <= ts:
            lo = mid + 1
        else:
            hi = mid
    if lo == 0:
        return False
    return active_at[keys[lo - 1]]


def _bucket(trades):
    if not trades:
        return {"n": 0}
    return {
        "n": len(trades),
        "expectancy_r": round(sum(float(t["r_multiple"]) for t in trades) / len(trades), 4),
        "chop": sum(t.get("weather") == "CHOP" for t in trades),
    }


if __name__ == "__main__":
    main()
