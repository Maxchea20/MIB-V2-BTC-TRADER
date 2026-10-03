"""Split the locked Hunt V3 book by Hunt weather (swing or chop) and by year. No new backtest.

Usage: py scripts\\diagnose_v3_regime.py [hunt trades.csv] [arbiter trades.csv]
Defaults to the newest file of each. Run it right after backtest_hunt_chop.py.
"""

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _latest(folder):
    return sorted((ROOT / "results" / folder).glob("*/trades.csv"))[-1]


def _read(path):
    return list(csv.DictReader(path.open(encoding="utf-8")))


def _line(label, rows):
    if not rows:
        return f"  {label:<22} n=0"
    equity = peak = dip = 0.0
    for r in rows:
        equity += float(r["r_multiple"])
        peak = max(peak, equity)
        dip = min(dip, equity - peak)
    total = sum(float(r["r_multiple"]) for r in rows)
    return f"  {label:<22} n={len(rows):<5} avg={total / len(rows):+.3f}R total={total:+.0f}R dip={dip:.1f}R"


def _year(row):
    return datetime.fromtimestamp(int(row["entry_time"]) / 1000, timezone.utc).strftime("%Y")


def _group(rows, key):
    out = {}
    for r in rows:
        out.setdefault(key(r), []).append(r)
    return dict(sorted(out.items()))


def main():
    hunt_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _latest("exp-hunt-desktop-cfi-v1")
    arb_path = Path(sys.argv[2]) if len(sys.argv) > 2 else _latest("exp-hunt-chop-arbiter")
    hunt = _read(hunt_path)
    weather = {r["entry_time"]: r["weather"] for r in hunt}
    arb = _read(arb_path)
    for r in arb:
        r["weather"] = weather.get(r["entry_time"], "") if r["book"] == "HUNT" else "BOX"
    print(f"hunt {hunt_path.parent.name}  switch {arb_path.parent.name}")
    print("Full Hunt by weather")
    for k, rows in _group(hunt, lambda r: r["weather"]).items():
        print(_line(k, rows))
    print("Switch by weather (BOX = chop trades)")
    for k, rows in _group(arb, lambda r: r["weather"]).items():
        print(_line(k, rows))
    print("Switch by year")
    for k, rows in _group(arb, _year).items():
        print(_line(k, rows))
    print("Switch by year and book")
    for k, rows in _group(arb, lambda r: (_year(r), r["book"])).items():
        print(_line(f"{k[0]} {k[1]}", rows))
    print("Full Hunt by year")
    for k, rows in _group(hunt, _year).items():
        print(_line(k, rows))


main()
