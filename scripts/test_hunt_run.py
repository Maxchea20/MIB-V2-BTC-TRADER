"""Let the winners run. Same Hunt entries and 1.5 ATR stop, but no 2.5 ATR target: a trailing stop sells the trade instead.

The per-trade check showed 25% of Hunt trades reach +4R and 10% reach +12R before their -1R stop, while the target sells every winner at +1.67R.
That best R is not capturable (you cannot sell the exact top), so this test trails the best price and counts what is really kept.
  base            stop 1.5 ATR, target 2.5 ATR (Hunt now)
  floors          Hunt V4's floors, target 2.5 ATR
  run trail X     no target, a trailing stop X R behind the best price from the start (1R = 1.5 ATR)
  floors + run X  the floors, then no target and a trailing stop X R behind the best price once the trade is 2.5 ATR in favor
Fee 2 bp a side. A trade still open at the end of the data is sold at the last close.
Usage: py scripts\\test_hunt_run.py research_2022_25
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

FLOORS = ((1.75, 1.5), (2.25, 2.0))


def variants():
    out = [("base", dict(tiers=())), ("floors", dict(tiers=FLOORS))]
    for x in (1.0, 1.5, 2.0, 3.0):
        out.append((f"run trail {x:g}R", dict(tiers=(), notarget=True, trail=(0.0, 1.5 * x))))
    for x in (1.0, 1.5, 2.0, 3.0):
        out.append((f"floors + run {x:g}R", dict(tiers=FLOORS, notarget=True, trail=(2.5, 1.5 * x))))
    return out


def run(bars, trades, cfg):
    times = [b.open_time for b in bars]
    rs = []
    for t in trades:
        entry, stop = float(t["entry"]), float(t["stop"])
        risk = abs(entry - stop)
        trade = {"side": t["side"], "entry": entry, "stop": stop, "target": float(t["target"]), "atr": risk / 1.5, "risk": risk}
        start = int(t["entry_time"])
        done = hunt_exits.walk(trade, bars, start, bars[-1].open_time + 60_000, cfg)
        if done is None:
            last = bars[-1].close
            done = hunt_exits._close(trade, last, bars[-1].open_time, "END")
        rs.append(done["r_multiple"])
    return rs


def stats(rs):
    eq = peak = dip = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dip = min(dip, eq - peak)
    total = sum(rs)
    return f"avg {total / len(rs):+.3f}R  total {total:+.0f}R  dip {dip:.1f}R  R/dip {total / abs(dip):.1f}  win {sum(r > 0.05 for r in rs) / len(rs):.0%}  >=2R {sum(r >= 2 for r in rs) / len(rs):.0%}  >=4R {sum(r >= 4 for r in rs) / len(rs):.0%}  best {max(rs):.0f}R"


def main():
    name = sys.argv[1]
    text = (ROOT / "results" / "lock3" / f"{name}_hunt.txt").read_text(encoding="utf-8", errors="replace")
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    if not file.is_absolute():
        file = ROOT / file
    trades = list(csv.DictReader(file.open(encoding="utf-8")))
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    print(f"{name}: {len(trades)} Hunt trades, same entries, different exits")
    for label, cfg in variants():
        print(f"  {label:<18} {stats(run(bars, trades, cfg))}")


if __name__ == "__main__":
    main()
