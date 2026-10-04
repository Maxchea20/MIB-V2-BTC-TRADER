"""Hunt V4 with small changes aimed at the worst drops. No new Hunt run.

The forensic showed: the chop book loses 0 of 31 trades inside the worst drawdowns, and entries at 04-08h UTC are among the
worst two hour blocks in all three files. Each variant rebuilds the one-position order, so skipped trades free the engine.
  no chop            Hunt outside the box only
  no 04-08h          no entries (Hunt or chop) from 04:00 to 08:00 UTC
  chop min risk X%   chop trades only when the stop is at least X% of price away (a tight stop makes the fee big in R)
  chop half          chop trades at half size
Usage: py scripts\\test_v4_tweaks.py research_2022_25
"""

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample

YEAR = {"research_2019_21": "2020", "research_2022_25": "2022", "research_binance": "2025"}


def _hour(t):
    return datetime.fromtimestamp(int(t["entry_time"]) / 1000, timezone.utc).hour


def _first_year(path):
    with path.open(encoding="utf-8") as handle:
        row = next(csv.DictReader(handle), None)
    return datetime.fromtimestamp(int(row["entry_time"]) / 1000, timezone.utc).strftime("%Y") if row else ""


def _stats(trades):
    rs = [float(t["r_multiple"]) for t in trades]
    eq = peak = dip = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dip = min(dip, eq - peak)
    total = sum(rs)
    chop = sum(t["book"] == "CHOP" for t in trades)
    return f"n={len(rs)} (chop {chop}) {total / len(rs):+.3f}R total={total:+.0f}R dip={dip:.1f}R R/dip={total / abs(dip):.1f}"


def variants(kept, chop, one_position):
    no_asia = lambda t: not 4 <= _hour(t) < 8
    out = {"Hunt V4": one_position(kept, chop)}
    out["no chop"] = one_position(kept, [])
    out["no 04-08h"] = one_position([t for t in kept if no_asia(t)], [t for t in chop if no_asia(t)])
    out["no chop, no 04-08h"] = one_position([t for t in kept if no_asia(t)], [])
    for pct in (0.003, 0.005):
        out[f"chop min risk {pct:.1%}"] = one_position(kept, [t for t in chop if t["risk"] / t["entry"] >= pct])
    half = one_position(kept, chop)
    out["chop half"] = [dict(t, r_multiple=float(t["r_multiple"]) * (0.5 if t["book"] == "CHOP" else 1.0)) for t in half]
    return out


def main():
    name = sys.argv[1]
    folder = ROOT / "results" / "exp-hunt-desktop-cfi-floors"
    files = [f for f in sorted(folder.glob("*/trades.csv")) if _first_year(f) == YEAR[name]]
    if not files:
        raise SystemExit("no floors Hunt file for this period. Run: py scripts\\run_floor_v3.py " + name + " floors")
    hunt = list(csv.DictReader(files[-1].open(encoding="utf-8")))
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    series = resample(bars, "1h")
    import backtest_hunt_chop as hc
    active = hc._flags(series)
    keys = sorted(active)
    kept = [t for t in hunt if not hc._on(int(t["entry_time"]), active, keys, hc.HOUR)]
    for t in kept:
        t["book"] = "HUNT"
    print(f"{name} Hunt V4 and tweaks ({files[-1].parent.name})")
    for label, trades in variants(kept, hc._chop(series, active), hc._one_position).items():
        print(f"  {label:<20} {_stats(trades)}")


if __name__ == "__main__":
    main()
