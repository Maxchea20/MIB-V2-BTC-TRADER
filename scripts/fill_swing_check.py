"""Hunt as a SWING trade, real fill. Same signals (the 5m close through the level, direction from the 4H/1H weather), entry at the next 1m open + slippage.
The only change: R (the stop distance) is sized from the 1H or 4H ATR instead of the 15m ATR, stop = 1.5 x that ATR, target = M x the stop. Plain stop/target, one position, 15 min pause.
Prints per line: trades, avg R, total R, dip, the stop as % of price, and the average holding time.
Usage: py scripts\\fill_swing_check.py research_2022_25
"""

import bisect
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.setups import hunt_exits

import backtest_desktop_cfi as eng
from fill_gap_check import NONE, _stats

TFS = (("1h", 3_600_000), ("4h", 14_400_000))
MS = (2.0, 3.0, 4.0, 6.0)
PAUSE = 15 * 60_000


def run(bars, trades, tf_bars, atrs, span, m):
    times = [b.open_time for b in bars]
    end = bars[-1].open_time + 60_000
    rs, stops, holds, free = [], [], [], 0
    for t in trades:
        sign = 1 if t["side"] == "LONG" else -1
        ts = int(t["entry_time"])
        if ts < free:
            continue
        i = bisect.bisect_left(times, ts)
        j = eng._closed(tf_bars, ts, span)
        if i >= len(bars) or i < 5 or j < 20 or not atrs[j - 1]:
            continue
        fill = bars[i].open + sign * (0.1 + bars[i].open * 0.00005)
        risk = 1.5 * atrs[j - 1]
        tr = {"side": t["side"], "atr": risk / 1.5, "entry": fill, "stop": fill - sign * risk, "target": fill + sign * risk * m, "risk": risk}
        done = hunt_exits.walk(tr, bars, ts, end, NONE)
        if not done:
            break
        free = done["exit_time"] + PAUSE
        rs.append(done["r_multiple"])
        stops.append(risk / fill)
        holds.append((done["exit_time"] - ts) / 3_600_000)
    return rs, stops, holds


def main():
    name = sys.argv[1]
    text = (ROOT / "results" / "lock3" / f"{name}_hunt.txt").read_text(encoding="utf-8", errors="replace")
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    if not file.is_absolute():
        file = ROOT / file
    trades = sorted(csv.DictReader(file.open(encoding="utf-8")), key=lambda r: int(r["entry_time"]))
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    print(f"{name}: {len(trades)} Hunt signals, real fill, stop = 1.5 x ATR of the timeframe shown")
    for tf, span in TFS:
        series = resample(bars, tf)
        atrs = eng._atr(series)
        for m in MS:
            rs, stops, holds = run(bars, trades, series, atrs, span, m)
            if not rs:
                print(f"  {tf} ATR  target {m}R  no trades")
                continue
            print(f"  {tf} ATR  target {m}R  " + _stats(rs) + f"  stop {100 * sum(stops) / len(stops):.2f}% of price  avg hold {sum(holds) / len(holds):.1f}h")


if __name__ == "__main__":
    main()
