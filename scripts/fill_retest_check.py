"""Hunt with a REALISTIC entry: after the 5m candle closes through the level, rest a limit order AT the broken level and only trade if price comes back to it.
No fill = no trade (the order is cancelled after WAIT minutes, or at once if price runs 1R away without touching the level, or goes through the stop).
Same signals, same 1R stop / 1.67R target (levels placed from the limit price), same exits as the Hunt run. Fees as in the backtest (taker both sides = conservative; a limit entry is really maker).
Prints, for WAIT = 15 / 60 / 240 minutes: how many fill, results of the filled trades, and what the trades you MISSED would have made (at the old fill-at-level backtest).
Usage: py scripts\\fill_retest_check.py research_2022_25
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
from fill_gap_check import FLOORS, NONE, _stats

WAITS = (15, 60, 240)


def analyze(bars, trades, wait):
    times = [b.open_time for b in bars]
    end = bars[-1].open_time + 60_000
    got = {"plain": [], "floors": [], "missed_orig": [], "filled_orig": []}
    for t in trades:
        entry, stop = float(t["entry"]), float(t["stop"])
        sign = 1 if t["side"] == "LONG" else -1
        risk0 = abs(entry - stop)
        ts = int(t["entry_time"])
        i = bisect.bisect_left(times, ts)
        if i >= len(bars) or i < 5:
            continue
        orig = float(t["r_multiple"])
        fill_i = None
        for j in range(i, min(len(bars), i + wait)):
            b = bars[j]
            touched = b.low < entry if sign == 1 else b.high > entry
            if touched:
                fill_i = j
                break
            ran = (b.high - entry) >= risk0 if sign == 1 else (entry - b.low) >= risk0
            if ran:
                break
        if fill_i is None:
            got["missed_orig"].append(orig)
            continue
        got["filled_orig"].append(orig)
        base = {"side": t["side"], "atr": risk0 / 1.5}
        for key, cfg in (("plain", NONE), ("floors", FLOORS)):
            tr = dict(base, entry=entry, stop=stop, target=entry + sign * risk0 * 5 / 3, risk=risk0)
            done = hunt_exits.walk(tr, bars, bars[fill_i].open_time, end, cfg) or hunt_exits._close(tr, bars[-1].close, bars[-1].open_time, "END")
            got[key].append(done["r_multiple"])
    return got


def avg(rs):
    return f"avg {sum(rs) / len(rs):+.3f}R" if rs else "-"


def main():
    name = sys.argv[1]
    text = (ROOT / "results" / "lock3" / f"{name}_hunt.txt").read_text(encoding="utf-8", errors="replace")
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    if not file.is_absolute():
        file = ROOT / file
    trades = list(csv.DictReader(file.open(encoding="utf-8")))
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    print(f"{name}: {len(trades)} Hunt signals")
    for w in WAITS:
        g = analyze(bars, trades, w)
        n = len(g["plain"])
        print(f"  limit at the level, wait {w} min: filled {n} ({n / len(trades):.0%}), missed {len(g['missed_orig'])}")
        print(f"    filled, same exit      " + _stats(g["plain"]) if n else "    nothing filled")
        if n:
            print(f"    filled, V4 floors      " + _stats(g["floors"]))
            print(f"    (old backtest on these filled trades {avg(g['filled_orig'])}; on the MISSED trades {avg(g['missed_orig'])})")


if __name__ == "__main__":
    main()
