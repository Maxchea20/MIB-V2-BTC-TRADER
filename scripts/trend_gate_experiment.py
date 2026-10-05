"""One pre-declared experiment: Hunt only in the direction of the 1H trend (gate=4h: the 4H trend), realistic execution (market order after the closed 5m signal + latency, simulated exits).
1H trend = the last closed 1H close vs the close 20 1H bars earlier. Hunt's own conditions are unchanged; a FIRE against the trend is FILTERED_TREND_GATE.
Four runs (floors on, same strategy otherwise):
  A0  Hunt, ATR unit 15m (as designed)          A1  the same, 1H-trend gate
  B0  Hunt, ATR unit 1H (stop about 1% of price) B1  the same, 1H-trend gate
Each prints trades/day, hold, win rate, avg R, PF(R), total R, dip, years positive, and the direction information after the fill (excess move over market drift, bp; cost about 5 bp).
Usage: py scripts\\trend_gate_experiment.py research_binance [gate=1h|4h] [latency=1] [intrabar=conservative]
"""

import bisect
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.execution.options import config_from_args

import backtest_desktop_cfi as eng
import daytrade_check as dt

DAY_MS = 86_400_000


def summary(label, trades, days):
    rs = [float(t["r_multiple"]) for t in trades]
    if not rs:
        return f"  {label:<30} no trades"
    eq = peak = dip = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dip = min(dip, eq - peak)
    wins, losses = sum(r for r in rs if r > 0), -sum(r for r in rs if r < 0)
    years = {}
    for t in trades:
        y = datetime.fromtimestamp(int(t["entry_time"]) / 1000, timezone.utc).year
        years[y] = years.get(y, 0.0) + float(t["r_multiple"])
    hold = sum(int(t["exit_time"]) - int(t["entry_time"]) for t in trades) / len(trades) / 3_600_000
    return (f"  {label:<30} {len(rs) / days:4.2f}/day hold {hold:5.1f}h  win {sum(r > 0 for r in rs) / len(rs):3.0%}  avg {sum(rs) / len(rs):+.3f}R  "
            f"PF(R) {wins / losses if losses else 9.99:4.2f}  total {sum(rs):+5.0f}R  dip {dip:6.1f}R  years +{sum(v > 0 for v in years.values())}/{len(years)}")


def main():
    cfg, rest = config_from_args(sys.argv[1:])
    tf = next((a.split("=", 1)[1] for a in rest if a.startswith("gate=")), "1h")
    rest = [a for a in rest if not a.startswith("gate=")]
    name = rest[0] if rest else "research_binance"
    T = tf.upper()
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    times = [b.open_time for b in bars]
    r = [resample(bars, x) for x in ("5m", "15m", "1h", "4h")]
    days = (bars[-1].open_time - bars[0].open_time) / DAY_MS
    print(f"{name}: {days:.0f} days. Realistic execution: latency {cfg.execution_latency_seconds}s, same-bar stop+target {cfg.intrabar_policy}. {T} trend = last closed {T} close vs the close 20 {T} bars earlier.")
    out = {}
    for key, gate, unit in (("A0", None, "15m"), ("A1", (tf, 20), "15m"), ("B0", None, "1h"), ("B1", (tf, 20), "1h")):
        events = []
        out[key] = (eng._run(bars, *r, False, None, False, "floors", False, cfg, events, False, gate, unit), events)
        print(f"  ... {key} done", flush=True)
    labels = {"A0": "A0 ungated, 15m ATR unit", "A1": f"A1 {T}-trend gate, 15m ATR unit", "B0": "B0 ungated, 1H ATR unit", "B1": f"B1 {T}-trend gate, 1H ATR unit"}
    print()
    for key in ("A0", "A1", "B0", "B1"):
        trades, events = out[key]
        print(summary(labels[key], trades, days))
    print("\nFIREs: ", end="")
    for key in ("A1", "B1"):
        ev = out[key][1]
        c = {}
        for e in ev:
            c[e["status"]] = c.get(e["status"], 0) + 1
        print(f"{key} total {len(ev)} {c}   ", end="")
    print("\n\ndirection after the fill (excess over market drift, bp; cost about 5 bp):")
    for key in ("A0", "A1"):
        adapted = [{"t": int(t["entry_time"]), "entry": float(t["entry"]), "side": t["side"]} for t in out[key][0]]
        print(f"  {labels[key]:<30} {dt.direction_info(bars, times, adapted)}")


if __name__ == "__main__":
    main()
