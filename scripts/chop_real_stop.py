"""Chop book alone, two ways. The chop entry is a real fill (next 1h open after the reject bar). The old STOP booked the exit AT THE LINE,
but the stop rule is a 1h CLOSE through the line, so the real exit is the close (plus slippage), usually worse than the line.
  old   stop booked at the line, exit time = start of the breaking bar
  real  stop booked at the close of the breaking bar minus slippage, exit time = end of that bar
Usage: py scripts\\chop_real_stop.py   (all three research files)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample

import backtest_hunt_chop as hc


def line(rows):
    b = hc._bucket(rows)
    if not b["n"]:
        return "no trades"
    total = b["n"] * b["expectancy_r"]
    stops = sum(1 for t in rows if t["exit_reason"] == "STOP")
    return f"n={b['n']} avg {b['expectancy_r']:+.3f}R total {total:+.0f}R dip {b['drawdown_r']:.1f}R  stops {stops}"


for name in ("research_2019_21", "research_2022_25", "research_binance"):
    path = ROOT / "backend" / f"{name}.db"
    if not path.exists():
        print(f"{name}: no database")
        continue
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    series = resample(bars, "1h")
    active = hc._flags(series)
    print(name)
    for label, real in (("old (stop at the line)  ", False), ("real (stop at the close)", True)):
        hc.REAL_STOP = real
        print(f"  {label} " + line(hc._chop(series, active)))
