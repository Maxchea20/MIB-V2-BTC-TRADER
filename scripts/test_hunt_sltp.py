"""Different stop and target sizes for the Hunt entries. Same entries as your Hunt run. No ATR talk: everything is in R.

R = today's stop distance. Today is SL 1R : TP 1.67R. Each variant risks the same dollars per trade, so a trade's R is measured against that variant's own stop,
and total R from different variants can be compared (total R x your risk = dollars).
"floors" are scaled with the target: the stop moves up when the trade is 70% of the way to the target (to 60% of the way), and again at 90% (to 80% of the way).
Today's floors are exactly this (TP 1.67R: arm at 1.17R and 1.5R, floors at 1.0R and 1.33R).
Fee 2 bp a side. Entries are fixed, so shorter or longer trades do not change which signals are taken.
Usage: py scripts\\test_hunt_sltp.py research_2022_25
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.setups import hunt_exits

COMBOS = ((1.0, 5 / 3), (1.0, 2.0), (1.0, 3.0), (1.5, 3.0), (1.5, 4.5), (2.0, 4.0))
U = 1.5  # one R of today = 1.5 ATR, the unit hunt_exits works in


def floors_cfg(tp_r):
    tp = tp_r * U
    return dict(tiers=((0.7 * tp, 0.6 * tp), (0.9 * tp, 0.8 * tp)))


def run(bars, trades, sl_r, tp_r, floors):
    cfg = floors_cfg(tp_r) if floors else dict(tiers=())
    rs = []
    for t in trades:
        entry, stop = float(t["entry"]), float(t["stop"])
        risk0 = abs(entry - stop)
        sign = 1 if t["side"] == "LONG" else -1
        trade = {"side": t["side"], "entry": entry, "stop": entry - sign * sl_r * risk0, "target": entry + sign * tp_r * risk0,
                 "atr": risk0 / U, "risk": sl_r * risk0}
        done = hunt_exits.walk(trade, bars, int(t["entry_time"]), bars[-1].open_time + 60_000, cfg)
        if done is None:
            done = hunt_exits._close(trade, bars[-1].close, bars[-1].open_time, "END")
        rs.append(done["r_multiple"])
    return rs


def stats(rs):
    eq = peak = dip = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dip = min(dip, eq - peak)
    total = sum(rs)
    return f"avg {total / len(rs):+.3f}R  total {total:+.0f}R  dip {dip:.1f}R  R/dip {total / abs(dip):.1f}  win {sum(r > 0.05 for r in rs) / len(rs):.0%}"


def main():
    name = sys.argv[1]
    text = (ROOT / "results" / "lock3" / f"{name}_hunt.txt").read_text(encoding="utf-8", errors="replace")
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    if not file.is_absolute():
        file = ROOT / file
    trades = list(csv.DictReader(file.open(encoding="utf-8")))
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    print(f"{name}: {len(trades)} Hunt trades, same entries. R = today's stop distance. Each variant risks the same $ per trade")
    for sl, tp in COMBOS:
        for floors in (False, True):
            label = f"SL {sl:g}R : TP {tp:.2f}R" + (" + floors" if floors else "")
            tag = "  (today)" if (sl, tp) == (1.0, 5 / 3) and not floors else ("  (Hunt V4's Hunt exit)" if (sl, tp) == (1.0, 5 / 3) else "")
            print(f"  {label:<26} {stats(run(bars, trades, sl, tp, floors))}{tag}")


if __name__ == "__main__":
    main()
