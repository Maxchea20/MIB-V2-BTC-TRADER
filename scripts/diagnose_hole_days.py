"""When the hole trades sat inside the failed-push box."""

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
    if not files:
        raise SystemExit("no full Hunt trades")
    trades = [t for t in csv.DictReader(files[-1].open(encoding="utf-8")) if HOLE_START <= int(t["entry_time"]) < HOLE_END]
    bars, _info = load_bars(db, "BTC_USDT", None, None)
    rows = []
    for name, span, lookback in (("1h", "1h", 240), ("4h", "4h", 180)):
        series = resample(bars, span)
        active = _flags(series, lookback)
        inside = [t for t in trades if _on(int(t["entry_time"]), active)]
        rows.append({"clock": name, "n": len(inside), "days": _days(inside)})
    print(json.dumps({"rows": rows}, indent=2))


def _flags(series, lookback):
    out = {}
    for i in range(lookback, len(series)):
        state = detect_push_range(series[i - lookback + 1 : i + 1])
        out[series[i].open_time] = state.active and state.phase == "RANGE"
    return out


def _on(ts, active):
    keys = sorted(active)
    lo, hi = 0, len(keys)
    while lo < hi:
        mid = (lo + hi) // 2
        if keys[mid] <= ts:
            lo = mid + 1
        else:
            hi = mid
    return bool(lo and active[keys[lo - 1]])


def _days(trades):
    out = {}
    for trade in trades:
        key = datetime.fromtimestamp(int(trade["entry_time"]) / 1000, timezone.utc).strftime("%Y-%m-%d")
        out[key] = out.get(key, 0) + 1
    return out


if __name__ == "__main__":
    main()
