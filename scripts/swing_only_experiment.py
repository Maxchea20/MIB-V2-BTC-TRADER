"""Chop removed. Hunt only in SWING weather (SWING_UP: longs only, SWING_DOWN: shorts only, as Hunt already does), no chop-weather trades, no box, no chop book.
Realistic execution (market order after the closed 5m signal + latency, simulated exits), floors on. Nothing else about Hunt is changed or tuned.
Two sizes: 15m ATR unit (Hunt as designed) and 1H ATR unit (stop about 1% of price). Each is split by CHoCH / BOS and by side, as numbers only.
'gross' = before slippage and fees, 'net' = after. Compare with the earlier all-weather results: -0.182R (15m unit) and -0.065R (1H unit) on research_binance.
Usage: py scripts\\swing_only_experiment.py research_binance [latency=1]
"""

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

DAY_MS = 86_400_000


def line(label, trades, days):
    if not trades:
        return f"  {label:<26} no trades"
    rs = [float(t["r_multiple"]) for t in trades]
    gs = [float(t["gross_r_before_costs"]) for t in trades]
    eq = peak = dip = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dip = min(dip, eq - peak)
    wins, losses = sum(r for r in rs if r > 0), -sum(r for r in rs if r < 0)
    yrs = {}
    for t in trades:
        y = datetime.fromtimestamp(int(t["entry_time"]) / 1000, timezone.utc).year
        yrs[y] = yrs.get(y, 0.0) + float(t["r_multiple"])
    hold = sum(int(t["exit_time"]) - int(t["entry_time"]) for t in trades) / len(trades) / 3_600_000
    return (f"  {label:<26} n={len(rs):4d} {len(rs) / days:4.2f}/day hold {hold:4.1f}h  win {sum(r > 0 for r in rs) / len(rs):3.0%}  gross {sum(gs) / len(gs):+.3f}R  net {sum(rs) / len(rs):+.3f}R  "
            f"PF(R) {wins / losses if losses else 9.99:4.2f}  total {sum(rs):+5.0f}R  dip {dip:6.1f}R  years +{sum(v > 0 for v in yrs.values())}/{len(yrs)}")


def main():
    cfg, rest = config_from_args(sys.argv[1:])
    name = rest[0] if rest else "research_binance"
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    r = [resample(bars, x) for x in ("5m", "15m", "1h", "4h")]
    days = (bars[-1].open_time - bars[0].open_time) / DAY_MS
    print(f"{name}: {days:.0f} days. Swing weather only, realistic execution (latency {cfg.execution_latency_seconds}s), floors on.")
    for unit, label in (("15m", "15m ATR unit (Hunt as designed)"), ("1h", "1H ATR unit (stop about 1% of price)")):
        events = []
        trades = eng._run(bars, *r, False, None, False, "floors", False, cfg, events, False, None, unit, True)
        c = {}
        for e in events:
            c[e["status"]] = c.get(e["status"], 0) + 1
        print(f"\nSWING ONLY, {label}")
        print(f"  FIREs {len(events)}: {c}")
        print(line("all swing trades", trades, days))
        for ev in ("CHoCH", "BOS"):
            print(line(f"  {ev}", [t for t in trades if t["event"] == ev], days))
        for w in ("SWING_UP", "SWING_DOWN"):
            print(line(f"  {w}", [t for t in trades if t["weather"] == w], days))
        for g in ("cfast", "internal", "rearm"):
            print(line(f"  gate {g}", [t for t in trades if t["gate"] == g], days))
        print("  ... done", flush=True)


if __name__ == "__main__":
    main()
