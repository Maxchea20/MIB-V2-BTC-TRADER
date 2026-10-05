"""Breakout, then retest: does waiting for the retest give a better ENTRY than buying the breakout? Information test only: no stop, no target, no exit.
Pre-declared definition (nothing tuned):
  breakout   a Hunt FIRE, unchanged (side, level = last closed 15m high/low, closed 5m candle beyond it). One watch at a time: a FIRE during an active watch is ignored.
  retest     after the FIRE, a closed 5m candle whose low (long) / high (short) comes back to within 0.10 ATR of the level AND that closes beyond the level (it held).
  entry      market order at the next 1m open after the retest candle closed (+ latency + slippage)
  cancelled  FAILED_BREAKOUT: a closed 5m candle closes more than 0.25 ATR back through the level;  RAN_AWAY: price trades 2 ATR beyond the level before any retest;  EXPIRED: no retest in 24 5m candles (2 hours)
For each horizon: how far price moves in the trade direction after the fill, excess over market drift, in bp (cost about 5 bp round trip), for
  IMMEDIATE  buying the breakout at once (every watch)         RETEST  the retest entries
  SAME, IMMEDIATE  the same signals as RETEST, entered at once   NO RETEST  the breakouts that never came back (what waiting misses), entered at once
Usage: py scripts\\retest_entry_screen.py research_binance [latency=1]
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
from btc_research.data.resample import resample
from btc_research.execution import market_fill
from btc_research.execution.options import config_from_args

import backtest_desktop_cfi as eng

FIVE = eng.FIVE
TOUCH, FAIL, RUN, WINDOW = 0.10, 0.25, 2.0, 24
HORIZONS = ((15, "15m"), (60, "1h"), (240, "4h"), (720, "12h"))


def watch_retest(b5, times5, signal_time, side, level, atr):
    """Returns (outcome, retest_candle). outcome: RETEST | FAILED_BREAKOUT | RAN_AWAY | EXPIRED."""
    i = bisect.bisect_left(times5, signal_time)
    for b in b5[i:i + WINDOW]:
        if side == "LONG":
            if b.close < level - FAIL * atr:
                return "FAILED_BREAKOUT", None
            if b.high >= level + RUN * atr:
                return "RAN_AWAY", None
            if b.low <= level + TOUCH * atr and b.close > level:
                return "RETEST", b
        else:
            if b.close > level + FAIL * atr:
                return "FAILED_BREAKOUT", None
            if b.low <= level - RUN * atr:
                return "RAN_AWAY", None
            if b.high >= level - TOUCH * atr and b.close < level:
                return "RETEST", b
    return "EXPIRED", None


def fwd(bars, times, ts, price, minutes):
    j = bisect.bisect_left(times, ts + minutes * 60_000)
    return None if j >= len(bars) else (bars[j].open - price) / price * 1e4


def cell(xs):
    n = len(xs)
    if n < 3:
        return f"{n:4d}      -"
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    return f"{n:4d} {m:+5.1f}bp t{m / (sd / math.sqrt(n)) if sd else 0:+4.1f}"


def main():
    cfg, rest = config_from_args(sys.argv[1:])
    name = rest[0] if rest else "research_binance"
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    times = [b.open_time for b in bars]
    r = [resample(bars, x) for x in ("5m", "15m", "1h", "4h")]
    b5 = r[0]
    times5 = [b.open_time for b in b5]
    events = []
    eng._run(bars, *r, False, None, False, "floors", False, cfg, events)
    drift = {}
    for minutes, _ in HORIZONS:
        xs = [v for v in (fwd(bars, times, bars[i].open_time, bars[i].open, minutes) for i in range(0, len(bars), 15)) if v is not None]
        drift[minutes] = sum(xs) / len(xs)

    watches, busy_until = [], 0
    for f in events:
        if f["signal_time"] < busy_until:
            continue
        side, level, atr = f["signal_side"], f["signal_level"], f["atr"]
        outcome, rb = watch_retest(b5, times5, f["signal_time"], side, level, atr)
        imm = market_fill(bars, times, side, f["signal_time"] + cfg.latency_ms, cfg, True, f["signal_price"])
        ret = market_fill(bars, times, side, rb.close_time + cfg.latency_ms, cfg, True, rb.close) if rb else None
        busy_until = (rb.close_time if rb else f["signal_time"] + WINDOW * FIVE)
        if imm.status != "FILLED":
            continue
        watches.append({"f": f, "outcome": outcome, "imm": imm, "ret": ret if ret and ret.status == "FILLED" else None})
    c = {}
    for w in watches:
        c[w["outcome"]] = c.get(w["outcome"], 0) + 1
    print(f"{name}: {len(watches)} breakout watches (one at a time). Outcomes: {c}")
    got = [w for w in watches if w["ret"]]
    if got:
        better = [(1 if w["f"]["signal_side"] == "LONG" else -1) * (w["imm"].fill_price - w["ret"].fill_price) / w["imm"].fill_price * 1e4 for w in got]
        print(f"  retest entries are {sum(better) / len(better):+.1f} bp better than buying the breakout at once (median {sorted(better)[len(better) // 2]:+.1f} bp)")

    def excess(w, which, minutes):
        fill = w[which]
        sign = 1 if w["f"]["signal_side"] == "LONG" else -1
        x = fwd(bars, times, fill.fill_time, fill.fill_price, minutes)
        return None if x is None else sign * (x - sign * drift[minutes])

    def col(ws, which, minutes):
        return [v for v in (excess(w, which, minutes) for w in ws) if v is not None]

    for title, subset in (("ALL weather", watches), ("SWING weather only", [w for w in watches if w["f"]["weather"] in ("SWING_UP", "SWING_DOWN")])):
        sub_got = [w for w in subset if w["ret"]]
        sub_miss = [w for w in subset if not w["ret"]]
        print(f"\n{title}: {len(subset)} watches, {len(sub_got)} retested ({len(sub_got) / max(1, len(subset)):.0%})")
        print(f"  {'horizon':<8}{'IMMEDIATE (all)':>22}{'RETEST entry':>22}{'SAME, IMMEDIATE':>22}{'NO RETEST, imm.':>22}")
        for minutes, label in HORIZONS:
            print(f"  {label:<8}{cell(col(subset, 'imm', minutes)):>22}{cell(col(sub_got, 'ret', minutes)):>22}{cell(col(sub_got, 'imm', minutes)):>22}{cell(col(sub_miss, 'imm', minutes)):>22}")


if __name__ == "__main__":
    main()
