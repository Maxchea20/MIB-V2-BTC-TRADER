"""Eye v2 on the Hunt V3 Hunt trades. Same entries, stop 1.5 ATR, target 2.5 ATR fixed. No halves.

Once price has reached 2.0 ATR the eye switches on:
  floor    the trade can no longer close below +2.0 ATR (the stop moves up to +2.0 ATR, from the next minute on).
           "fl1R" variants put the floor at +1.5 ATR (1R) instead, which gives the eye room to work above it
  closed   at each closed 15m candle: structure / stall / reversal rules (same as eye v1)
  forming  at each 1m close, looking at the 15m candle still forming:
             pullback = price has dropped pb ATR from the best price (it pushed higher, then rolled back)
             sell candle = the forming candle so far has a body over half its range, is over 0.5 ATR tall,
                           is below its open and sits in its bottom third
Any eye signal sells at the next 1m open. Trades that never reach 2.0 ATR are untouched.
Fee 2 bp a side. Stop wins when a bar touches the stop and the target.
Usage: py scripts\\test_hunt_eye2.py research_2022_25
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

SCHEMES = [
    ("base 2.5", dict()),
    ("target 2.0", dict(target=2.0)),
    ("floor 2.0 only", dict(floor=True)),
    ("eye closed", dict(floor=True, closed=True)),
    ("eye forming 0.2", dict(floor=True, forming=True, pb=0.2)),
    ("eye both 0.2", dict(floor=True, closed=True, forming=True, pb=0.2)),
    ("eye both 0.1", dict(floor=True, closed=True, forming=True, pb=0.1)),
    ("eye both 0.3", dict(floor=True, closed=True, forming=True, pb=0.3)),
    ("floor 1R only", dict(floor=True, floor_at=1.5)),
    ("eye both 0.2 fl1R", dict(floor=True, floor_at=1.5, closed=True, forming=True, pb=0.2)),
    ("eye both 0.3 fl1R", dict(floor=True, floor_at=1.5, closed=True, forming=True, pb=0.3)),
]
ARM = 2.0
TARGET = 2.5


def _closed_fires(candles, last_high_idx):
    c = candles[-1]
    struct = len(candles) >= 4 and c["cl"] < min(x["lo"] for x in candles[-4:-1])
    stall = len(candles) - 1 - last_high_idx >= 4
    return struct or stall or _sell_candle(c, None)


def _sell_candle(c, min_span):
    span = c["hi"] - c["lo"]
    if span <= 0 or (min_span is not None and span < min_span):
        return False
    return abs(c["cl"] - c["op"]) / span >= 0.5 and c["cl"] < c["op"] and c["cl"] <= c["lo"] + span / 3


def replay(bars, i, trade, cfg):
    sign = 1 if trade["side"] == "LONG" else -1
    entry, stop = float(trade["entry"]), float(trade["stop"])
    risk = abs(entry - stop)
    atr = risk / 1.5
    e = sign * entry
    stop_p = sign * stop
    target = cfg.get("target", TARGET)
    best = e
    candles, cur = [], None
    last_high_idx = 0
    pending = None
    last = e
    reason = "TIME"
    price = e
    for bar in bars[i:i + 4320]:
        hi = bar.high if sign == 1 else -bar.low
        lo = bar.low if sign == 1 else -bar.high
        op, cl = sign * bar.open, sign * bar.close
        last = cl
        armed = best >= e + ARM * atr
        key = bar.open_time // 900_000
        if cur is not None and cur["key"] != key:
            candles.append(cur)
            cur = None
            if armed and cfg.get("closed") and _closed_fires(candles, last_high_idx):
                pending = "EYE-C"
        if cur is None:
            cur = {"key": key, "op": op, "hi": hi, "lo": lo, "cl": cl}
        else:
            cur["hi"], cur["lo"], cur["cl"] = max(cur["hi"], hi), min(cur["lo"], lo), cl
        if pending:
            price, reason = op, pending
            break
        if lo <= stop_p:
            price, reason = stop_p, ("FLOOR" if stop_p > sign * stop else "SL")
            break
        if hi >= e + target * atr:
            price, reason = e + target * atr, "TP"
            break
        if hi > best:
            best = hi
            last_high_idx = len(candles)
        armed = best >= e + ARM * atr
        if armed and cfg.get("floor"):
            stop_p = max(stop_p, e + cfg.get("floor_at", ARM) * atr)
        if armed and cfg.get("forming"):
            if best - cl >= cfg["pb"] * atr or _sell_candle(cur, 0.5 * atr):
                pending = "EYE-F"
    else:
        price = last
    gross = price - e
    fees = (entry + sign * price) * 0.0002
    return (gross - fees) / risk, reason


def main():
    name = sys.argv[1]
    db = research_db_path(f"backend/{name}.db")
    text = (ROOT / "results" / "lock3" / f"{name}_switch.txt").read_text(encoding="utf-8", errors="replace")
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    if not file.is_absolute():
        file = ROOT / file
    trades = [t for t in csv.DictReader(file.open(encoding="utf-8")) if t["book"] == "HUNT"]
    bars, _ = load_bars(db, "BTC_USDT", None, None)
    times = [b.open_time for b in bars]
    starts = [bisect.bisect_left(times, int(t["entry_time"])) for t in trades]
    original = sum(float(t["r_multiple"]) for t in trades) / len(trades)
    print(f"{name} Hunt V3 Hunt trades, {len(trades)} trades, file avg {original:+.3f}R. Eye v2: arms at 2.0 ATR, TP stays 2.5 ATR")
    for label, cfg in SCHEMES:
        out = [replay(bars, i, t, cfg) for i, t in zip(starts, trades)]
        rs = [r for r, _ in out]
        equity = peak = dip = 0.0
        for r in rs:
            equity += r
            peak = max(peak, equity)
            dip = min(dip, equity - peak)
        counts = {}
        for _, why in out:
            counts[why] = counts.get(why, 0) + 1
        why = " ".join(f"{k}{counts[k]}" for k in ("TP", "FLOOR", "EYE-C", "EYE-F", "SL", "TIME") if k in counts)
        big = sum(r >= 1.0 for r in rs)
        print(f"  {label:<16} avg {sum(rs) / len(rs):+.3f}R total {sum(rs):+.0f}R dip {dip:.1f}R  wins>=1R {big}  | {why}")


if __name__ == "__main__":
    main()
