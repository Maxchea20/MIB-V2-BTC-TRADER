"""Is the Hunt entry price really tradable? The backtest fills at the broken 15m level (plus a small slippage). The signal is a 5m candle
that CLOSES through the level, so by the time you know the signal the market may be well past the level: the entry can be "in mid air".

For every Hunt trade this checks:
  mid air   the entry price was not traded at all inside the 5m signal candle (for a long: below the candle's low)
  gap       how far the next 1m open (the first price you could really get) is from the entry price, in R (R = the trade's stop distance)
Then it re-runs the trades with a realistic fill: a market order at the next 1m open plus the same slippage.
  levels moved   stop and target are placed from the real fill, same distances as before (same 1R stop, 1.67R target)
  levels kept    stop and target stay where the backtest put them, so the real fill makes the stop wider and the target closer
Same entries as your Hunt run, same exits. Usage: py scripts\\fill_gap_check.py research_2022_25
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
from btc_research.setups import hunt_exits

FIVE = 300_000
FLOORS = dict(tiers=((1.75, 1.5), (2.25, 2.0)))
NONE = dict(tiers=())


def _stats(rs):
    eq = peak = dip = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dip = min(dip, eq - peak)
    total = sum(rs)
    return f"n={len(rs)} avg {total / len(rs):+.3f}R total {total:+.0f}R dip {dip:.1f}R R/dip {total / abs(dip) if dip else 0:.1f}"


def analyze(bars, trades):
    times = [b.open_time for b in bars]
    end = bars[-1].open_time + 60_000
    out = {"mid": 0, "gaps": [], "orig": [], "moved": [], "moved_f": [], "kept": [], "skipped": 0}
    for t in trades:
        entry, stop = float(t["entry"]), float(t["stop"])
        sign = 1 if t["side"] == "LONG" else -1
        risk0 = abs(entry - stop)
        ts = int(t["entry_time"])
        i = bisect.bisect_left(times, ts)
        if i >= len(bars) or i < 5:
            continue
        candle = bars[bisect.bisect_left(times, ts - FIVE):i]
        if candle and ((sign == 1 and entry < min(b.low for b in candle)) or (sign == -1 and entry > max(b.high for b in candle))):
            out["mid"] += 1
        slip = 0.1 + bars[i].open * 0.00005
        fill = bars[i].open + sign * slip
        out["gaps"].append((fill - entry) * sign / risk0)
        out["orig"].append(float(t["r_multiple"]))
        base = {"side": t["side"], "atr": risk0 / 1.5}
        for key, cfg in (("moved", NONE), ("moved_f", FLOORS)):
            tr = dict(base, entry=fill, stop=fill - sign * risk0, target=fill + sign * risk0 * 5 / 3, risk=risk0)
            done = hunt_exits.walk(tr, bars, ts, end, cfg) or hunt_exits._close(tr, bars[-1].close, bars[-1].open_time, "END")
            out[key].append(done["r_multiple"])
        risk_kept = (fill - stop) * sign
        if risk_kept <= 0:
            out["skipped"] += 1
            out["kept"].append(-1.0)
            continue
        tr = dict(base, entry=fill, stop=stop, target=float(t["target"]), risk=risk_kept)
        done = hunt_exits.walk(tr, bars, ts, end, NONE) or hunt_exits._close(tr, bars[-1].close, bars[-1].open_time, "END")
        out["kept"].append(done["r_multiple"])
    return out


def report(name, out):
    g = sorted(out["gaps"])
    n = len(g)
    pick = lambda q: g[min(n - 1, int(q * n))]
    print(f"{name}: {n} Hunt entries")
    print(f"  entry price not traded inside the 5m signal candle (mid air): {out['mid'] / n:.0%}")
    print(f"  fill gap, next 1m open vs the entry price, in R (+ = worse for you): median {pick(.5):+.2f}  75th {pick(.75):+.2f}  90th {pick(.9):+.2f}  worse than 0.25R: {sum(x > .25 for x in g) / n:.0%}  worse than 0.5R: {sum(x > .5 for x in g) / n:.0%}")
    print("  results (same exit: stop 1R, target 1.67R):")
    print("    as in the backtest (fill at the level)        " + _stats(out["orig"]))
    print("    real fill, levels moved with the fill          " + _stats(out["moved"]))
    print("    real fill, levels kept where the backtest set them " + _stats(out["kept"]) + (f"  ({out['skipped']} already through the stop)" if out["skipped"] else ""))
    print("    real fill, levels moved, with Hunt V4's floors  " + _stats(out["moved_f"]))


def main():
    name = sys.argv[1]
    text = (ROOT / "results" / "lock3" / f"{name}_hunt.txt").read_text(encoding="utf-8", errors="replace")
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    if not file.is_absolute():
        file = ROOT / file
    trades = list(csv.DictReader(file.open(encoding="utf-8")))
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    report(name, analyze(bars, trades))


if __name__ == "__main__":
    main()
