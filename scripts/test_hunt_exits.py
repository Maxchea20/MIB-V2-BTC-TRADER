"""Replay the Hunt V3 Hunt trades with different exits. Same entries, same stop (1.5 ATR). No new Hunt run.

Schemes (ATR from entry; stop is always 1.5 ATR first):
  base        target 2.5 ATR                                (what Hunt V3 does now)
  T2.0 ...    a smaller fixed target
  half@X BE   sell half at X ATR, stop to entry for the rest, rest runs to 2.5 ATR
  half@X      sell half at X ATR, stop stays, rest runs to 2.5 ATR
  trail       once 1.4 ATR is reached, trail 1.0 ATR behind the best price; still capped at 2.5 ATR
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
]


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

    def sell(frac, price_p):
        nonlocal left, pnl, fees
        pnl += frac * (price_p - e)
        fees += frac * (entry + sign * price_p) * 0.0002
        left -= frac

    for bar in bars[i:i + 4320]:
        hi = bar.high if sign == 1 else -bar.low
        lo = bar.low if sign == 1 else -bar.high
        last = sign * bar.close
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
        best = max(best, hi)
        if "arm" in cfg and best >= e + cfg["arm"] * atr:
            stop_p = max(stop_p, best - cfg["dist"] * atr)
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
