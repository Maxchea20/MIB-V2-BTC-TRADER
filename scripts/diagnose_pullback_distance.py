"""How far price comes back after the 20-bar break. No trades."""

import json
import sqlite3
import statistics
from pathlib import Path

MS_5 = 300_000


def main():
    db = Path("backend/research_binance.db")
    bars_1m = _load(db)
    bars_5 = _resample(bars_1m, 5)
    bars_15 = _resample(bars_1m, 15)
    atr = _atr(bars_15, 14)
    rows = []
    bias = None
    for i, bar in enumerate(bars_5):
        if i < 50:
            continue
        window = bars_5[i - 50:i]
        prior_high = max(b[2] for b in window)
        prior_low = min(b[3] for b in window)
        side = level = None
        if bar[4] > prior_high:
            side, level = "LONG", prior_high
            bias = "LONG"
        elif bar[4] < prior_low:
            side, level = "SHORT", prior_low
            bias = "SHORT"
        if side is None or _sign(bars_15, bar[1], 20) != side:
            continue
        atr_v = _latest(bars_15, atr, bar[1])
        if not atr_v:
            continue
        future = bars_5[i + 1:i + 7]
        if not future:
            continue
        if side == "LONG":
            dip = min(b[3] for b in future)
            retrace = max(0.0, bar[4] - dip)
            touched = dip <= level
        else:
            pop = max(b[2] for b in future)
            retrace = max(0.0, pop - bar[4])
            touched = pop >= level
        rows.append({"side": side, "atr": retrace / atr_v, "touched": touched, "bias": bias})
    print(json.dumps({"n": len(rows), "combined": _block(rows), "long": _block([r for r in rows if r["side"] == "LONG"]), "short": _block([r for r in rows if r["side"] == "SHORT"])}, indent=2))


def _block(rows):
    if not rows:
        return {"n": 0}
    vals = [r["atr"] for r in rows]
    return {
        "n": len(rows),
        "touch_level": round(sum(r["touched"] for r in rows) / len(rows), 3),
        "median_retrace_atr": round(statistics.median(vals), 3),
        "retrace_0.25_atr": round(sum(v >= 0.25 for v in vals) / len(rows), 3),
        "retrace_0.50_atr": round(sum(v >= 0.50 for v in vals) / len(rows), 3),
        "retrace_1.00_atr": round(sum(v >= 1.00 for v in vals) / len(rows), 3),
    }


def _load(db):
    con = sqlite3.connect(db)
    found = con.execute("SELECT ts, open, high, low, close FROM candles WHERE symbol='BTC_USDT' AND timeframe='1m' ORDER BY ts").fetchall()
    con.close()
    return [(int(ts) * 1000, float(o), float(h), float(l), float(c)) for ts, o, h, l, c in found]


def _resample(bars, minutes):
    width = minutes * 60_000
    out = []
    bucket = None
    for ts, o, h, l, c in bars:
        start = ts - (ts % width)
        if bucket is None or bucket[0] != start:
            if bucket:
                out.append(bucket)
            bucket = [start, start + width, o, h, l, c]
        else:
            bucket[3] = max(bucket[3], h)
            bucket[4] = min(bucket[4], l)
            bucket[5] = c
    if bucket:
        out.append(bucket)
    return out


def _sign(bars, now, lookback):
    closed = [b for b in bars if b[1] <= now]
    if len(closed) <= lookback:
        return None
    window = closed[-1 - lookback:-1]
    bar = closed[-1]
    if bar[5] > max(b[3] for b in window):
        return "LONG"
    if bar[5] < min(b[4] for b in window):
        return "SHORT"
    return None


def _atr(bars, period):
    out = [None] * len(bars)
    prev = bars[0][5]
    trs = []
    for i, bar in enumerate(bars):
        tr = max(bar[3] - bar[4], abs(bar[3] - prev), abs(bar[4] - prev))
        prev = bar[5]
        trs.append(tr)
        if i >= period:
            out[i] = sum(trs[i - period + 1:i + 1]) / period
    return out


def _latest(bars, values, now):
    got = None
    for bar, value in zip(bars, values):
        if bar[1] > now:
            break
        if value:
            got = value
    return got


if __name__ == "__main__":
    main()
