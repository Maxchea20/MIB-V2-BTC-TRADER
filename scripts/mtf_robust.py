"""Is the real-fill swing breakout robust, or did we just pick a lucky setting?
Signal: 15m close beyond the prior 20-bar high (long) / low (short), both sides, entry = market order at the next 1m open. Stop = SL x 4h ATR, target = TPR x stop.
Grid: gates (4h+1h released, or 1h released with the 4h trend kept) x stop size SL x target TPR. Each row: trades, avg R, total R, worst dip, and how many calendar years are positive.
Then a cost stress on the main setting: fee 2 bp -> 4 bp a side (the docs baseline), slippage 0.5 bp -> 2 bp.
A real edge should look similar in the neighbouring cells, not live in one cell.
Usage: py scripts\\mtf_robust.py [backend\\research_2022_25.db]
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.setups.mtf_stack import run_mtf

BASE = json.loads((ROOT / "config" / "experiments" / "exp-mtf-open-bothany-4R.json").read_text())
GATES = (("both released", "any", "any"), ("1h released, 4h trend kept", "trend", "any"))
SLS = (1.0, 1.5, 2.0)
TPRS = (2, 3, 4, 5, 6)


def stats(trades):
    if not trades:
        return "no trades"
    rs = [t["r_multiple"] for t in trades]
    eq = peak = dip = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dip = min(dip, eq - peak)
    years = {}
    for t in trades:
        y = datetime.fromtimestamp(t["entry_time"] / 1000, timezone.utc).year
        years[y] = years.get(y, 0.0) + t["r_multiple"]
    pos = sum(v > 0 for v in years.values())
    return f"n={len(rs):4d} avg {sum(rs) / len(rs):+.3f}R total {sum(rs):+5.0f}R dip {dip:6.1f}R  years +{pos}/{len(years)}"


def main():
    db = research_db_path(sys.argv[1] if len(sys.argv) > 1 else None)
    bars, _ = load_bars(db, BASE.get("symbol") or "BTCUSDT", None, None)
    b15, b1h, b4h = (resample(bars, x) for x in ("15m", "1h", "4h"))
    both = ["LONG", "SHORT"]
    print(f"{db.name}: market order at the next 1m open, stop = SL x 4h ATR, target = TPR x stop")

    def run(**kw):
        trades, _ = run_mtf(bars, b15, b1h, b4h, dict(BASE, **kw), both)
        return sorted(trades, key=lambda t: t["entry_time"])

    for label, g4, g1 in GATES:
        print(f"\n{label}")
        for sl in SLS:
            for tpr in TPRS:
                print(f"  stop {sl:.1f} ATR  target {tpr}R  " + stats(run(h4_gate=g4, h1_gate=g1, sl_atr=sl, tp_atr=sl * tpr)))
    print("\ncost stress, both released, stop 1.5 ATR, target 4R")
    for label, kw in (("as tested (fee 2bp, slip 0.5bp)", {}), ("fee 4bp", {"fee_bps_per_side": 4.0}), ("slip 2bp", {"slippage_bps": 2.0}), ("fee 4bp + slip 2bp", {"fee_bps_per_side": 4.0, "slippage_bps": 2.0})):
        print(f"  {label:<34}" + stats(run(h4_gate="any", h1_gate="any", sl_atr=1.5, tp_atr=6.0, **kw)))


if __name__ == "__main__":
    main()
