"""Eye v2 on the Hunt V3 Hunt trades. Same entries, stop 1.5 ATR, target 2.5 ATR fixed. No halves.

Two zones:
  zone B  best price between 1.5 ATR (1R) and 2.0 ATR: if the trade turns down, close it at the best available price, never below +1R
  zone A  best price from 2.0 ATR up: if it will not reach 2.5 ATR, close it, never below +2.0 ATR
A floor is a stop that moves up. "cushion" variants arm a floor 0.25 ATR above its level (1R floor arms at 1.75 ATR,
the 2.0 ATR floor arms at 2.25 ATR), because a floor armed exactly at its own level is hit by the first pullback.
The eye (when on) sells at the next 1m open after:
  closed   a closed 15m candle shows structure break / stall / a sell candle
  forming  at each 1m close, the 15m candle still forming: price has dropped pb ATR from the best price,
           or the candle so far is a sell candle (body over half its range, over 0.5 ATR tall, bottom third, below its open)
Trades that never reach the first arm level are untouched (stop at -1R).
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
    ("target 1.5", dict(target=1.5)),
    ("floor 2.0 + eye .2", dict(floor=True, closed=True, forming=True, pb=0.2)),
    ("zones + eye .2", dict(tiers=((1.5, 1.5), (2.0, 2.0)), arm=1.5, closed=True, forming=True, pb=0.2)),
    ("zones cushion", dict(tiers=((1.75, 1.5), (2.25, 2.0)))),
    ("zones cushion eye .1", dict(tiers=((1.75, 1.5), (2.25, 2.0)), arm=1.75, closed=True, forming=True, pb=0.1)),
    ("zones cushion eye .2", dict(tiers=((1.75, 1.5), (2.25, 2.0)), arm=1.75, closed=True, forming=True, pb=0.2)),
    ("zones cushion eye .25", dict(tiers=((1.75, 1.5), (2.25, 2.0)), arm=1.75, closed=True, forming=True, pb=0.25)),
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
        armed = best >= e + cfg.get("arm", ARM) * atr
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
            best = max(best, hi)
            break
        if hi >= e + target * atr:
            price, reason = e + target * atr, "TP"
            best = max(best, hi)
            break
        if hi > best:
            best = hi
            last_high_idx = len(candles)
        armed = best >= e + cfg.get("arm", ARM) * atr
        if cfg.get("tiers"):
            for arm_level, floor_level in cfg["tiers"]:
                if best >= e + arm_level * atr:
                    stop_p = max(stop_p, e + floor_level * atr)
        elif best >= e + ARM * atr and cfg.get("floor"):
            stop_p = max(stop_p, e + cfg.get("floor_at", ARM) * atr)
        if armed and cfg.get("forming"):
            if best - cl >= cfg["pb"] * atr or _sell_candle(cur, 0.5 * atr):
                pending = "EYE-F"
    else:
        price = last
    gross = price - e
    fees = (entry + sign * price) * 0.0002
    return (gross - fees) / risk, reason, (best - e) / atr


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
    print(f"{name} Hunt V3 Hunt trades, {len(trades)} trades, file avg {original:+.3f}R. Eye v2, TP stays 2.5 ATR")
    for label, cfg in SCHEMES:
        out = [replay(bars, i, t, cfg) for i, t in zip(starts, trades)]
        rs = [r for r, _, _ in out]
        equity = peak = dip = 0.0
        for r in rs:
            equity += r
            peak = max(peak, equity)
            dip = min(dip, equity - peak)
        counts = {}
        for _, why, _ in out:
            counts[why] = counts.get(why, 0) + 1
        why = " ".join(f"{k}{counts[k]}" for k in ("TP", "FLOOR", "EYE-C", "EYE-F", "SL", "TIME") if k in counts)
        big = sum(r >= 0.95 for r in rs)
        if label == "base 2.5":
            reach = {lvl: sum(m >= lvl for _, _, m in out) for lvl in (1.0, 1.5, 2.0, 2.5)}
            print("  reached before the trade ended: " + "  ".join(f"{lvl} ATR {n} ({n / len(out):.0%})" for lvl, n in reach.items()))
        print(f"  {label:<18} avg {sum(rs) / len(rs):+.3f}R total {sum(rs):+.0f}R dip {dip:.1f}R  wins>=0.95R {big}  | {why}")


if __name__ == "__main__":
    main()
