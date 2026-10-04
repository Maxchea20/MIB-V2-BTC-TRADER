"""Hunt with a REAL fill (market order at the next 1m open after the 5m signal closes, plus slippage) and WIDER stops.
Why: the fill gap and the fees are fixed in dollars, so a bigger stop makes them a smaller part of 1R.
Stop = K x the old 1R distance (K = 2, 3, 4, 6). Target = M x that stop (M = 2.5, 4, 6, 8). ONE position at a time, 15 min pause after an exit. No floors, no trailing, plain stop/target.
Usage: py scripts\\fill_wide_stop_check.py research_2022_25
"""

import bisect
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.setups import hunt_exits
from fill_gap_check import NONE, _stats

KS = (2.0, 3.0, 4.0, 6.0)
MS = (2.5, 4.0, 6.0, 8.0)
PAUSE = 15 * 60_000


def run(bars, trades, k, m):
    times = [b.open_time for b in bars]
    end = bars[-1].open_time + 60_000
    rs = []
    free = 0
    for t in trades:
        entry, stop = float(t["entry"]), float(t["stop"])
        sign = 1 if t["side"] == "LONG" else -1
        risk0 = abs(entry - stop)
        ts = int(t["entry_time"])
        if ts < free:
            continue
        i = bisect.bisect_left(times, ts)
        if i >= len(bars) or i < 5:
            continue
        fill = bars[i].open + sign * (0.1 + bars[i].open * 0.00005)
        risk = risk0 * k
        tr = {"side": t["side"], "atr": risk0 / 1.5, "entry": fill, "stop": fill - sign * risk, "target": fill + sign * risk * m, "risk": risk}
        done = hunt_exits.walk(tr, bars, ts, end, NONE) or hunt_exits._close(tr, bars[-1].close, bars[-1].open_time, "END")
        free = done["exit_time"] + PAUSE
        rs.append(done["r_multiple"])
    return rs


def main():
    name = sys.argv[1]
    text = (ROOT / "results" / "lock3" / f"{name}_hunt.txt").read_text(encoding="utf-8", errors="replace")
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    if not file.is_absolute():
        file = ROOT / file
    trades = sorted(csv.DictReader(file.open(encoding="utf-8")), key=lambda r: int(r["entry_time"]))
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    print(f"{name}: {len(trades)} Hunt signals, real market fill. R = the new stop distance.")
    for k in KS:
        for m in MS:
            print(f"  stop {k}x  target {m}R   " + _stats(run(bars, trades, k, m)))


if __name__ == "__main__":
    main()
