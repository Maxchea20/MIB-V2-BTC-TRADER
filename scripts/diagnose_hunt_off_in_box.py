"""Hunt is dropped while the failed-push box is on. Chop keeps its own trades."""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.market_structure.failed_push_range import detect_push_range


def main():
    db = research_db_path(sys.argv[1] if len(sys.argv) > 1 else None)
    hunt_files = sorted((ROOT / "results" / "exp-hunt-desktop-cfi-v1").glob("*/trades.csv"))
    chop_files = sorted((ROOT / "results" / "exp-chop-zone-1h").glob("*/trades.csv"))
    if not hunt_files or not chop_files:
        raise SystemExit("need the Hunt file and the quarter chop file")
    hunt = list(csv.DictReader(hunt_files[-1].open(encoding="utf-8")))
    chop = list(csv.DictReader(chop_files[-1].open(encoding="utf-8")))
    bars, _info = load_bars(db, "BTC_USDT", None, None)
    series = resample(bars, "1h")
    active = {}
    for i in range(240, len(series)):
        state = detect_push_range(series[i - 239 : i + 1])
        active[series[i].open_time] = state.active and state.phase == "RANGE"
    kept = [t for t in hunt if not _on(int(t["entry_time"]), active)]
    print(json.dumps({
        "hunt": _bucket(hunt),
        "hunt_outside_box": _bucket(kept),
        "chop_zone": _bucket(chop),
        "combined": _bucket(kept + chop),
    }, indent=2))


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


def _bucket(rows):
    if not rows:
        return {"n": 0}
    return {
        "n": len(rows),
        "expectancy_r": round(sum(float(r["r_multiple"]) for r in rows) / len(rows), 4),
    }


if __name__ == "__main__":
    main()
