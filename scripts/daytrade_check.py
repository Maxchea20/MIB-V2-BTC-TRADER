"""Day-trade check. Goal: 1-2 trades a day, trades that live hours (not minutes, not days). Real fills only.
Rules (all fixed, nothing tuned on the result):
  direction  4H trend only: last closed 4H close vs the close 20 4H bars earlier. Up -> longs only, down -> shorts only.
  signal     brk15  a 15m close beyond the prior 20-bar high (long) / low (short)
             brk1h  a 1H close beyond the prior 20-bar high / low
             pull   a pullback of at least 0.75 x 1H ATR from the last 8 hours' extreme, then a 15m close back through the previous 15m bar's high/low
  entry      market order at the first 1m open after the signal bar closes, plus slippage (1 tick + 0.5 bp)
  stop       K x 1H ATR   target  M x the stop   time limit 12 hours (closed at market)
  limits     one position at a time, 15 minute pause after an exit, at most 2 entries per day (day = UTC+8, your chart)
  costs      2 bp fee a side, slippage on every exit too
Also prints, per signal, how far price moves in the signal direction after the fill (excess over market drift, bp; cost about 5 bp): that is the direction information, independent of stop and target.
Usage: py scripts\\daytrade_check.py backend\\research_2022_25.db     (no argument = research_binance)
"""

import bisect
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.setups.hunt_lookback import _atr, _slip
from btc_research.setups.mtf_stack import _n_closed

HOLD_MS = 12 * 3_600_000
PAUSE_MS = 15 * 60_000
TZ_MS = 8 * 3_600_000
DAY_MS = 86_400_000
MAX_PER_DAY = 2
CFG = {"slippage_ticks": 1, "tick_size": 0.1, "slippage_bps": 0.5}
FEE = 2.0 / 10_000
KS = (1.0, 1.5)
MS = (1.5, 2.0, 3.0)
TRIGGERS = ("brk15", "brk1h", "pull")


def signals(bars_1m, b15, b1h, b4h, atr1, trigger):
    """Every candidate (decision_time, side, atr) in time order. Causal: only bars closed by the decision time."""
    out = []
    for i in range(40, len(b15)):
        bar = b15[i]
        now = bar.close_time
        n4 = _n_closed(b4h, now)
        n1 = _n_closed(b1h, now)
        if n4 < 22 or n1 < 22 or not atr1[n1 - 1]:
            continue
        up, dn = b4h[n4 - 1].close, b4h[n4 - 21].close
        if up == dn:
            continue
        side = "LONG" if up > dn else "SHORT"
        sign = 1 if side == "LONG" else -1
        ok = False
        if trigger == "brk15":
            w = b15[i - 20:i]
            ok = bar.close > max(b.high for b in w) if sign == 1 else bar.close < min(b.low for b in w)
        elif trigger == "brk1h":
            if b1h[n1 - 1].close_time != now:
                continue
            w = b1h[n1 - 21:n1 - 1]
            ok = b1h[n1 - 1].close > max(b.high for b in w) if sign == 1 else b1h[n1 - 1].close < min(b.low for b in w)
        else:
            w8 = b15[i - 32:i]
            w4 = b15[i - 4:i]
            if sign == 1:
                depth = max(b.high for b in w8) - min(b.low for b in w4)
                ok = depth >= 0.75 * atr1[n1 - 1] and bar.close > b15[i - 1].high and bar.close < max(b.high for b in w8)
            else:
                depth = max(b.high for b in w4) - min(b.low for b in w8)
                ok = depth >= 0.75 * atr1[n1 - 1] and bar.close < b15[i - 1].low and bar.close > min(b.low for b in w8)
        if ok:
            out.append((now, side, atr1[n1 - 1]))
    return out


def simulate(bars, times, sigs, k, m):
    trades, free, per_day = [], 0, {}
    for now, side, atr in sigs:
        if now < free:
            continue
        i = bisect.bisect_left(times, now)
        if i >= len(bars) - 1:
            break
        day = (bars[i].open_time + TZ_MS) // DAY_MS
        if per_day.get(day, 0) >= MAX_PER_DAY:
            continue
        sign = 1 if side == "LONG" else -1
        entry = _slip(bars[i].open, side, CFG, True)
        risk = k * atr
        stop, target = entry - sign * risk, entry + sign * m * risk
        deadline = bars[i].open_time + HOLD_MS
        exit_px = exit_t = None
        for j in range(i, len(bars)):
            b = bars[j]
            if b.open_time >= deadline:
                exit_px, exit_t = b.open, b.open_time
                break
            if (b.low <= stop) if sign == 1 else (b.high >= stop):
                exit_px, exit_t = stop, b.close_time
                break
            if (b.high >= target) if sign == 1 else (b.low <= target):
                exit_px, exit_t = target, b.close_time
                break
        if exit_px is None:
            break
        exit_px = _slip(exit_px, side, CFG, False)
        net = sign * (exit_px - entry) - (entry + exit_px) * FEE
        per_day[day] = per_day.get(day, 0) + 1
        free = exit_t + PAUSE_MS
        trades.append({"t": bars[i].open_time, "x": exit_t, "side": side, "entry": entry, "r": net / risk})
    return trades


def stats(trades, days):
    if not trades:
        return "no trades"
    rs = [t["r"] for t in trades]
    eq = peak = dip = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dip = min(dip, eq - peak)
    wins, losses = sum(r for r in rs if r > 0), -sum(r for r in rs if r < 0)
    yrs = {}
    for t in trades:
        y = datetime.fromtimestamp(t["t"] / 1000, timezone.utc).year
        yrs[y] = yrs.get(y, 0.0) + t["r"]
    hold = sum(t["x"] - t["t"] for t in trades) / len(trades) / 3_600_000
    return (f"{len(rs) / days:4.2f}/day  hold {hold:4.1f}h  win {sum(r > 0 for r in rs) / len(rs):3.0%}  avg {sum(rs) / len(rs):+.3f}R  "
            f"PF(R) {wins / losses if losses else 9.99:4.2f}  total {sum(rs):+5.0f}R  dip {dip:6.1f}R  years +{sum(v > 0 for v in yrs.values())}/{len(yrs)}")


def direction_info(bars, times, trades):
    lines = []
    for minutes, label in ((60, "1h"), (240, "4h"), (720, "12h")):
        def fwd(ts, price):
            j = bisect.bisect_left(times, ts + minutes * 60_000)
            return None if j >= len(bars) else (bars[j].open - price) / price * 1e4
        drift = [r for r in (fwd(bars[i].open_time, bars[i].open) for i in range(0, len(bars), 15)) if r is not None]
        d = sum(drift) / len(drift)
        xs = []
        for t in trades:
            r = fwd(t["t"], t["entry"])
            if r is not None:
                s = 1 if t["side"] == "LONG" else -1
                xs.append(s * (r - s * d))
        if len(xs) > 2:
            mean = sum(xs) / len(xs)
            sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / (len(xs) - 1))
            lines.append(f"{label} {mean:+.1f}bp (t {mean / (sd / math.sqrt(len(xs))) if sd else 0:+.1f})")
    return "  ".join(lines)


def main():
    db = research_db_path(sys.argv[1] if len(sys.argv) > 1 else None)
    bars, _ = load_bars(db, "BTC_USDT", None, None)
    times = [b.open_time for b in bars]
    b15, b1h, b4h = (resample(bars, x) for x in ("15m", "1h", "4h"))
    atr1 = _atr(b1h, 14)
    days = (bars[-1].open_time - bars[0].open_time) / DAY_MS
    print(f"{db.name}: {days:.0f} days. 4H trend sets the side. Max {MAX_PER_DAY} trades a day (UTC+8), 12h time limit, real market fill, stop = K x 1H ATR.")
    for trig in TRIGGERS:
        sigs = signals(bars, b15, b1h, b4h, atr1, trig)
        print(f"\n{trig}: {len(sigs)} signals")
        for k in KS:
            for m in MS:
                print(f"  stop {k:.1f} ATR  target {m:.1f}R  " + stats(simulate(bars, times, sigs, k, m), days))
        print("  direction after the fill (stop 1.0 / 2.0R trades): " + direction_info(bars, times, simulate(bars, times, sigs, 1.0, 2.0)))


if __name__ == "__main__":
    main()
