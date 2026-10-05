"""Does the Hunt signal carry ANY directional information? No stop, no target, no exit design. Real fill (the engine's realfill entry).
For every real-fill Hunt entry: the move in the signal direction from the fill to +15m, +1h, +4h, +12h, +24h, +72h, in basis points of price.
Market drift is removed: the same horizon measured from every 15m in the file is the baseline d; a LONG is compared with +d, a SHORT with -d.
Costs for reference: 2 bp a side fee + slippage, about 5 bp round trip. An edge has to be bigger than that, and t (naive, signals overlap so be careful) should be well above 2.
Usage: py scripts\\hunt_forward_returns.py research_binance
"""

import bisect
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars

import hunt_entry_scan as scan

HORIZONS = ((15, "15m"), (60, "1h"), (240, "4h"), (720, "12h"), (1440, "24h"), (4320, "72h"))


def fwd(bars, times, ts, entry, minutes):
    i = bisect.bisect_left(times, ts + minutes * 60_000)
    return None if i >= len(bars) else (bars[i].open - entry) / entry * 1e4


def stat(xs):
    n = len(xs)
    if n < 2:
        return n, 0.0, 0.0, 0.0
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    return n, m, sum(x > 0 for x in xs) / n, (m / (sd / math.sqrt(n)) if sd else 0.0)


def main():
    name = sys.argv[1]
    trades = scan.trades_for(name)
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    times = [b.open_time for b in bars]
    print(f"{name}: {len(trades)} real-fill Hunt entries. Move in the signal direction, excess over market drift, in bp of price (cost about 5 bp)")
    print(f"  {'horizon':<8}{'n':>6}   {'ALL excess bp':>14} {'up%':>5} {'t':>6}   {'LONG excess':>12}   {'SHORT excess':>12}")
    for minutes, label in HORIZONS:
        drift = [r for r in (fwd(bars, times, bars[i].open_time, bars[i].open, minutes) for i in range(0, len(bars), 15)) if r is not None]
        d = sum(drift) / len(drift)
        per = {"LONG": [], "SHORT": []}
        for t in trades:
            sign = 1 if t["side"] == "LONG" else -1
            r = fwd(bars, times, int(t["entry_time"]), float(t["entry"]), minutes)
            if r is not None:
                per[t["side"]].append(sign * (r - sign * d))
        allx = per["LONG"] + per["SHORT"]
        n, m, up, tt = stat(allx)
        print(f"  {label:<8}{n:6d}   {m:+14.1f} {up:5.0%} {tt:+6.1f}   {stat(per['LONG'])[1]:+12.1f}   {stat(per['SHORT'])[1]:+12.1f}")


if __name__ == "__main__":
    main()
