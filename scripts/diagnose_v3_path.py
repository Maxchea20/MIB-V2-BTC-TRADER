"""How far each Hunt V3 trade went for and against before it ended. No new backtest.

MFE = best price in favor, MAE = worst price against, both in R (the stop distance).
1 ATR in favor = 0.667R for Hunt (stop is 1.5 ATR). The exit bar itself is left out.
Usage: py scripts\\diagnose_v3_path.py research_2022_25
"""

import bisect
import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars


def _paths(bars, trades):
    times = [b.open_time for b in bars]
    out = []
    for t in trades:
        entry, stop = float(t["entry"]), float(t["stop"])
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        lo = bisect.bisect_left(times, int(t["entry_time"]))
        hi = bisect.bisect_left(times, int(t["exit_time"]))
        window = bars[lo:hi]
        if not window:
            continue
        if t["side"] == "LONG":
            mfe = (max(b.high for b in window) - entry) / risk
            mae = (entry - min(b.low for b in window)) / risk
        else:
            mfe = (entry - min(b.low for b in window)) / risk
            mae = (max(b.high for b in window) - entry) / risk
        out.append({"book": t["book"], "reason": t["exit_reason"], "r": float(t["r_multiple"]), "mfe": max(mfe, 0), "mae": max(mae, 0), "mins": (int(t["exit_time"]) - int(t["entry_time"])) / 60_000})
    return out


def _share(rows, key, level):
    return f"{sum(r[key] >= level for r in rows) / len(rows):.0%}" if rows else "n/a"


def _med(rows, key):
    return f"{statistics.median(r[key] for r in rows):.2f}" if rows else "n/a"


def report(name, rows):
    print(f"{name} Hunt V3 trade path (R = stop distance; 1 ATR in favor = 0.67R for Hunt)")
    for book in ("HUNT", "CHOP"):
        for reason in ("STOP", "TARGET"):
            sub = [r for r in rows if r["book"] == book and r["reason"] == reason]
            if not sub:
                continue
            print(
                f"  {book:<4} {reason:<6} n={len(sub):<5} median MFE={_med(sub, 'mfe')}R MAE={_med(sub, 'mae')}R "
                f"time={_med(sub, 'mins')}min | reached +0.67R {_share(sub, 'mfe', 0.667)} +1R {_share(sub, 'mfe', 1.0)} +1.5R {_share(sub, 'mfe', 1.5)}"
            )
    stops = [r for r in rows if r["book"] == "HUNT" and r["reason"] == "STOP"]
    wins = [r for r in rows if r["book"] == "HUNT" and r["reason"] == "TARGET"]
    if stops and wins:
        print(f"  Hunt winners dipped past -0.5R first: {_share(wins, 'mae', 0.5)}   past -0.8R: {_share(wins, 'mae', 0.8)}")
        print(f"  Hunt stopped trades that were +0.67R up at some point: {_share(stops, 'mfe', 0.667)}")


def main():
    name = sys.argv[1]
    db = research_db_path(f"backend/{name}.db")
    text = (ROOT / "results" / "lock3" / f"{name}_switch.txt").read_text(encoding="utf-8", errors="replace")
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    if not file.is_absolute():
        file = ROOT / file
    trades = list(csv.DictReader(file.open(encoding="utf-8")))
    bars, _ = load_bars(db, "BTC_USDT", None, None)
    report(name, _paths(bars, trades))


if __name__ == "__main__":
    main()
