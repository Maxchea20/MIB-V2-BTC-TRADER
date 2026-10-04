"""Hunt V3: TP/SL counts, what price did after TP and after SL, and how far the move ran. No new backtest.

After TP / after SL: the 24 hours of 1m bars after the trade ended.
Swing run: from entry, follow the best price until it falls 1 stop distance (1R) from its peak (max 7 days).
Hunt units are ATR (stop = 1.5 ATR) and price. Chop has no ATR, so it is in R (stop distance) and price.
Usage: py scripts\\diagnose_v3_after_exit.py research_2022_25
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

AFTER_MIN = 1440
RUN_MIN = 7 * 1440


def _pct(vals, q):
    vals = sorted(vals)
    return vals[min(len(vals) - 1, int(q * len(vals)))] if vals else float("nan")


def _row(label, vals, unit):
    if not vals:
        return f"    {label:<34} n/a"
    return f"    {label:<34} median {_pct(vals, .5):.2f}  p75 {_pct(vals, .75):.2f}  p90 {_pct(vals, .9):.2f}  max {max(vals):.2f} {unit}"


def _measure(bars, times, t):
    side = 1 if t["side"] == "LONG" else -1
    entry, stop, target = float(t["entry"]), float(t["stop"]), float(t["target"])
    risk = abs(entry - stop)
    hunt = t["book"] == "HUNT"
    unit_size = risk / 1.5 if hunt else risk
    exit_time = int(t["exit_time"]) + (0 if hunt else 3_600_000)
    lo = bisect.bisect_right(times, exit_time)
    after = bars[lo:lo + AFTER_MIN]
    out = {"book": t["book"], "reason": t["exit_reason"], "unit": unit_size}
    if after:
        hi_p, lo_p = max(b.high for b in after), min(b.low for b in after)
        fav = lambda p: (p - entry) * side
        best, worst = (hi_p, lo_p) if side == 1 else (lo_p, hi_p)
        out["after_best"], out["after_worst"] = best, worst
        out["entry"], out["stop"], out["target"] = entry, stop, target
        out["side"] = side
    start = bisect.bisect_left(times, int(t["entry_time"]))
    peak = entry
    for b in bars[start:start + RUN_MIN]:
        if (peak - b.low if side == 1 else b.high - peak) >= risk and peak != entry:
            break
        peak = max(peak, b.high) if side == 1 else min(peak, b.low)
    out["run"] = (peak - entry) * side
    return out


def report(name, bars, trades):
    times = [b.open_time for b in bars]
    rows = [_measure(bars, times, t) for t in trades if float(t["entry"]) != float(t["stop"])]
    print(f"{name} Hunt V3: TP / SL counts, 24h after the exit, and the move size")
    for book, unit in (("HUNT", "ATR"), ("CHOP", "R")):
        sub = [r for r in rows if r["book"] == book]
        if not sub:
            continue
        tp = [r for r in sub if r["reason"] == "TARGET"]
        sl = [r for r in sub if r["reason"] == "STOP"]
        print(f"  {book}: TP {len(tp)} ({len(tp) / len(sub):.0%})   SL {len(sl)} ({len(sl) / len(sub):.0%})")
        tp = [r for r in tp if "after_best" in r]
        sl = [r for r in sl if "after_best" in r]
        if tp:
            beyond = [abs(r["after_best"] - r["target"]) / r["unit"] if (r["after_best"] - r["target"]) * r["side"] > 0 else 0 for r in tp]
            beyond_usd = [(r["after_best"] - r["target"]) * r["side"] for r in tp]
            back = sum((r["after_worst"] - r["entry"]) * r["side"] <= 0 for r in tp) / len(tp)
            print("  after TP, further move beyond the target:")
            print(_row(f"in {unit}", beyond, unit))
            print(_row("in price", [max(v, 0) for v in beyond_usd], "$"))
            print(f"    came all the way back to entry within 24h: {back:.0%}")
        if sl:
            further = [max((r["stop"] - r["after_worst"]) * r["side"], 0) / r["unit"] for r in sl]
            rec = [max((r["after_best"] - r["stop"]) * r["side"], 0) / r["unit"] for r in sl]
            to_entry = sum((r["after_best"] - r["entry"]) * r["side"] >= 0 for r in sl) / len(sl)
            to_target = sum((r["after_best"] - r["target"]) * r["side"] >= 0 for r in sl) / len(sl)
            print("  after SL:")
            print(_row(f"kept going past the stop, {unit}", further, unit))
            print(_row(f"bounced back toward entry, {unit}", rec, unit))
            print(f"    price got back to entry within 24h: {to_entry:.0%}   reached the target: {to_target:.0%}")
        run = [r["run"] / r["unit"] for r in sub]
        usd = [r["run"] for r in sub]
        print("  swing run from entry (until a 1R pullback from the peak):")
        print(_row(f"in {unit}", run, unit))
        print(_row("in price", usd, "$"))


def main():
    name = sys.argv[1]
    db = research_db_path(f"backend/{name}.db")
    text = (ROOT / "results" / "lock3" / f"{name}_switch.txt").read_text(encoding="utf-8", errors="replace")
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    if not file.is_absolute():
        file = ROOT / file
    trades = list(csv.DictReader(file.open(encoding="utf-8")))
    bars, _ = load_bars(db, "BTC_USDT", None, None)
    report(name, bars, trades)


if __name__ == "__main__":
    main()
