"""Why does the real fill lose, and can we fill EARLIER without cheating?

Part 1 (forensic): the Hunt trades from your saved Hunt run, split by how far the real fill is from the level (the gap, in R).
  Shows where the fake edge comes from: small-gap trades vs big-gap trades, fake-fill R vs real-fill R.
Part 2 (earlier entry, no future peeking): a resting STOP order at  level +/- X ATR  (X = 0, 0.15, 0.30), placed when the 15m slot opens.
  It fills the moment price touches it (at the trigger, or at the bar open if price gapped through it) + slippage. It does NOT wait for the 5m close,
  and it takes EVERY touch, including the ones that reverse (the old backtest only kept breakouts that later closed beyond the level).
  Same side/weather rules as Hunt, same stop 1.5 ATR / target 2.5 ATR, one position, 15 min pause after an exit. Exit "plain" and "floors" (V4's).
Usage: py scripts\\forensic_fill_early.py research_binance
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
import fill_gap_check as fg

FIFTEEN = eng.FIFTEEN
PAUSE = 15 * 60_000
OFFSETS = (0.0, 0.15, 0.30)
EXITS = {"plain": fg.NONE, "floors": fg.FLOORS}


def part1(bars, trades):
    out = fg.analyze(bars, trades)
    rows = sorted(zip(out["gaps"], out["orig"], out["moved"]))
    n = len(rows)
    print(f"PART 1: {n} Hunt trades by real-fill gap (gap = how much worse the real fill is than the level, in R)")
    print("  gap bucket          trades   fake-fill avg R   real-fill avg R")
    edges = [0, n // 4, n // 2, 3 * n // 4, n]
    for k in range(4):
        part = rows[edges[k]:edges[k + 1]]
        lo, hi = part[0][0], part[-1][0]
        print(f"  {lo:+.2f}R .. {hi:+.2f}R   {len(part):5d}      {sum(r[1] for r in part) / len(part):+.3f}           {sum(r[2] for r in part) / len(part):+.3f}")


def touch_run(bars, b5, b15, b1h, b4h, offset, exitcfg):
    times = [b.open_time for b in bars]
    end = bars[-1].open_time + 60_000
    atrs, atrs4 = eng._atr(b15), eng._atr(b4h)
    fast, internal = eng._events(b15, 5), eng._events(b15, 2)
    trades, free = [], 0
    for bar in b5:
        slot_start = (bar.open_time // FIFTEEN) * FIFTEEN
        if bar.open_time != slot_start or slot_start < free:
            continue
        j15 = eng._closed(b15, slot_start, FIFTEEN)
        j4 = eng._closed(b4h, slot_start, 14_400_000)
        j1 = eng._closed(b1h, slot_start, 3_600_000)
        if j15 < 60 or j4 < 20 or not atrs[j15 - 1]:
            continue
        side, event, gate = eng._gate(fast, internal, j15)
        if not side:
            continue
        flag = eng._weather(b4h[:j4], b1h[:j1], atrs4, None)
        if (flag == "SWING_UP" and side != "LONG") or (flag == "SWING_DOWN" and side != "SHORT"):
            continue
        atr = atrs[j15 - 1]
        sign = 1 if side == "LONG" else -1
        level = b15[j15 - 1].high if side == "LONG" else b15[j15 - 1].low
        trigger = level + sign * offset * atr
        i = bisect.bisect_left(times, slot_start)
        fill_i = None
        for k in range(i, min(len(bars), i + 15)):
            b = bars[k]
            if (b.high >= trigger) if sign == 1 else (b.low <= trigger):
                fill_i = k
                break
        if fill_i is None:
            continue
        b = bars[fill_i]
        px = max(trigger, b.open) if sign == 1 else min(trigger, b.open)
        entry = px + sign * (0.1 + px * 0.00005)
        tr = {"side": side, "atr": atr, "entry": entry, "stop": entry - sign * 1.5 * atr, "target": entry + sign * 2.5 * atr, "risk": 1.5 * atr}
        done = hunt_exits.walk(tr, bars, b.open_time, end, exitcfg)
        if not done:
            break
        trades.append(done)
        free = done["exit_time"] + PAUSE
    return trades


def part2(bars):
    b5, b15, b1h, b4h = (resample(bars, x) for x in ("5m", "15m", "1h", "4h"))
    print("\nPART 2: resting stop order, fills on touch (no waiting for the 5m close)")
    for off in OFFSETS:
        for name, cfg in EXITS.items():
            rs = [t["r_multiple"] for t in touch_run(bars, b5, b15, b1h, b4h, off, cfg)]
            print(f"  trigger level{off:+.2f}ATR  exit {name:<6} " + (fg._stats(rs) if rs else "no trades"))


def main():
    name = sys.argv[1]
    text = (ROOT / "results" / "lock3" / f"{name}_hunt.txt").read_text(encoding="utf-8", errors="replace")
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    if not file.is_absolute():
        file = ROOT / file
    trades = list(csv.DictReader(file.open(encoding="utf-8")))
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    print(name)
    part1(bars, trades)
    part2(bars)


if __name__ == "__main__":
    main()
