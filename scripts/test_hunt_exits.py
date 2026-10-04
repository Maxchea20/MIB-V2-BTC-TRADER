"""Replay the Hunt V3 Hunt trades with different exits. Same entries, same stop (1.5 ATR). No new Hunt run.

Schemes (ATR from entry; stop is always 1.5 ATR first):
  base        target 2.5 ATR                                (what Hunt V3 does now)
  T2.0 ...    a smaller fixed target
  half@X BE   sell half at X ATR, stop to entry for the rest, rest runs to 2.5 ATR
  half@X      sell half at X ATR, stop stays, rest runs to 2.5 ATR
  trail       once 1.4 ATR is reached, trail 1.0 ATR behind the best price; still capped at 2.5 ATR
  giveback    once 1.4 ATR is reached, exit if price gives back 40% of the best move
  eye ...     once 1.4 ATR is reached, watch the closed 15m candles and sell at the next 1m open when:
              structure = a 15m close below the lowest low of the 3 candles before it
              stall     = 4 closed 15m candles with no new best price (1 hour)
              reversal  = a 15m candle with a body over half its range, closing in its bottom third against the trade
              any       = any of the three
  eye hold    lets price hover sideways for as long as it likes. Exits only when a closed 15m candle ends
              more than 0.7 (or 1.0) ATR below the best price, so a pause is fine and a drop is not
Stop wins when a bar touches the stop and a level. Fee 2 bp a side on each fill. Max hold 3 days.
Usage: py scripts\\test_hunt_exits.py research_2022_25
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
    ("base 2.5", dict(target=2.5)),
    ("target 2.0", dict(target=2.0)),
    ("target 1.5", dict(target=1.5)),
    ("target 1.0", dict(target=1.0)),
    ("half@1.0 BE", dict(target=2.5, half=1.0, be=True)),
    ("half@1.4 BE", dict(target=2.5, half=1.4, be=True)),
    ("half@1.0", dict(target=2.5, half=1.0, be=False)),
    ("half@1.4", dict(target=2.5, half=1.4, be=False)),
    ("trail 1.4/1.0", dict(target=2.5, arm=1.4, dist=1.0)),
    ("giveback 40%", dict(target=2.5, arm=1.4, frac=0.4)),
    ("eye structure", dict(target=2.5, eye="struct", arm_eye=1.4)),
    ("eye stall", dict(target=2.5, eye="stall", arm_eye=1.4)),
    ("eye reversal", dict(target=2.5, eye="rev", arm_eye=1.4)),
    ("eye any", dict(target=2.5, eye="any", arm_eye=1.4)),
    ("eye hold 0.7", dict(target=2.5, eye="hold", arm_eye=1.4, hold=0.7)),
    ("eye hold 1.0", dict(target=2.5, eye="hold", arm_eye=1.4, hold=1.0)),
]


def _eye_fires(kind, candles, last_high_idx):
    c = candles[-1]
    struct = len(candles) >= 4 and c["cl"] < min(x["lo"] for x in candles[-4:-1])
    stall = len(candles) - 1 - last_high_idx >= 4
    span = c["hi"] - c["lo"]
    rev = span > 0 and abs(c["cl"] - c["op"]) / span >= 0.5 and c["cl"] < c["op"] and c["cl"] <= c["lo"] + span / 3
    return {"struct": struct, "stall": stall, "rev": rev, "any": struct or stall or rev}[kind]


def replay(bars, i, trade, cfg):
    sign = 1 if trade["side"] == "LONG" else -1
    entry, stop = float(trade["entry"]), float(trade["stop"])
    risk = abs(entry - stop)
    atr = risk / 1.5
    e = sign * entry
    stop_p = sign * stop
    best = e
    left = 1.0
    pnl = fees = 0.0
    half_done = False
    last = None
    eye = cfg.get("eye")
    candles = []
    cur = None
    last_high_idx = 0
    pending = False

    def sell(frac, price_p):
        nonlocal left, pnl, fees
        pnl += frac * (price_p - e)
        fees += frac * (entry + sign * price_p) * 0.0002
        left -= frac

    for bar in bars[i:i + 4320]:
        hi = bar.high if sign == 1 else -bar.low
        lo = bar.low if sign == 1 else -bar.high
        last = sign * bar.close
        if eye:
            key = bar.open_time // 900_000
            if cur is not None and cur["key"] != key:
                candles.append(cur)
                armed = best >= e + cfg["arm_eye"] * atr
                if armed and eye == "hold":
                    pending = best - candles[-1]["cl"] > cfg["hold"] * atr
                elif armed and _eye_fires(eye, candles, last_high_idx):
                    pending = True
                cur = None
            if cur is None:
                cur = {"key": key, "op": sign * bar.open, "hi": hi, "lo": lo, "cl": sign * bar.close}
            else:
                cur["hi"], cur["lo"], cur["cl"] = max(cur["hi"], hi), min(cur["lo"], lo), sign * bar.close
            if pending:
                sell(left, sign * bar.open)
                break
        if lo <= stop_p:
            sell(left, stop_p)
            break
        if "half" in cfg and not half_done and hi >= e + cfg["half"] * atr:
            sell(0.5, e + cfg["half"] * atr)
            half_done = True
            if cfg["be"]:
                stop_p = max(stop_p, e)
        if hi >= e + cfg["target"] * atr:
            sell(left, e + cfg["target"] * atr)
            break
        if hi > best:
            best = hi
            last_high_idx = len(candles)
        if "dist" in cfg and best >= e + cfg["arm"] * atr:
            stop_p = max(stop_p, best - cfg["dist"] * atr)
        if "frac" in cfg and best >= e + cfg["arm"] * atr:
            stop_p = max(stop_p, best - cfg["frac"] * (best - e))
    if left > 1e-9:
        sell(left, last if last is not None else e)
    return (pnl - fees) / risk


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
    print(f"{name} Hunt V3 Hunt trades, {len(trades)} trades, file avg {original:+.3f}R. Same entries, different exits")
    for label, cfg in SCHEMES:
        rs = [replay(bars, i, t, cfg) for i, t in zip(starts, trades)]
        equity = peak = dip = 0.0
        for r in rs:
            equity += r
            peak = max(peak, equity)
            dip = min(dip, equity - peak)
        wins = sum(r > 0 for r in rs) / len(rs)
        print(f"  {label:<14} avg {sum(rs) / len(rs):+.3f}R  total {sum(rs):+.0f}R  dip {dip:.1f}R  winners {wins:.0%}")


if __name__ == "__main__":
    main()
