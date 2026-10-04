"""How much of Hunt's edge do costs eat, and does it depend on how far away the stop is?

Fee in R = round-trip fee / stop distance, so a trade with a tight stop pays more R in fees than one with a wide stop.
For each fifth of the trades, sorted by stop distance (as a % of price): gross R (before the 2 bp a side fee), fee R, net R.
Then the net result if you only take trades whose stop is at least a given distance away.
Uses the Hunt trade file from your Hunt run (original exits: stop 1R, target 1.67R). Usage: py scripts\\fee_vs_stop_size.py research_2022_25
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    text = (ROOT / "results" / "lock3" / f"{name}_hunt.txt").read_text(encoding="utf-8", errors="replace")
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    if not file.is_absolute():
        file = ROOT / file
    rows = []
    for t in csv.DictReader(file.open(encoding="utf-8")):
        entry, stop, exit_ = float(t["entry"]), float(t["stop"]), float(t["exit"])
        risk = abs(entry - stop)
        fee = (entry + exit_) * 0.0002 / risk
        rows.append({"t": int(t["entry_time"]), "risk_pct": risk / entry * 100, "net": float(t["r_multiple"]), "fee": fee})
    return rows


def _stats(rs):
    eq = peak = dip = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dip = min(dip, eq - peak)
    total = sum(rs)
    return f"n={len(rs)} avg {total / len(rs):+.3f}R total {total:+.0f}R dip {dip:.1f}R R/dip {total / abs(dip) if dip else 0:.1f}"


def report(name, rows):
    ordered = sorted(rows, key=lambda x: x["risk_pct"])
    n = len(ordered)
    gross = sum(x["net"] + x["fee"] for x in rows) / n
    fee = sum(x["fee"] for x in rows) / n
    print(f"{name}: {n} Hunt trades. Average per trade: gross {gross:+.3f}R, fee {fee:.3f}R, net {gross - fee:+.3f}R  (fees take {fee / gross:.0%} of the gross edge)")
    print("  by stop distance (fifths, tightest to widest):")
    for k in range(5):
        part = ordered[k * n // 5:(k + 1) * n // 5]
        g = sum(x["net"] + x["fee"] for x in part) / len(part)
        f = sum(x["fee"] for x in part) / len(part)
        print(f"    stop {part[0]['risk_pct']:.2f}% to {part[-1]['risk_pct']:.2f}%   n={len(part):<5} gross {g:+.3f}R  fee {f:.3f}R  net {g - f:+.3f}R")
    print("  take only trades with a stop at least this far away:")
    for q in (0.0, 0.2, 0.4, 0.6):
        cut = ordered[int(q * n)]["risk_pct"]
        kept = sorted((x for x in rows if x["risk_pct"] >= cut), key=lambda x: x["t"])
        print(f"    stop >= {cut:.2f}%  " + _stats([x["net"] for x in kept]))


if __name__ == "__main__":
    report(sys.argv[1], load(sys.argv[1]))
