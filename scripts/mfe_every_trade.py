"""How many R does every Hunt trade reach? Each trade is followed from its entry until its own 1R stop (1.5 ATR against) is hit.
No target, no floors, so a trade that would have run far is allowed to run. Also writes one row per trade to results\\mfe\\.

R = the stop distance (1.5 ATR). 1R = 1.5 ATR, 1.33R = 2.0 ATR, 1.67R = 2.5 ATR (the target). Random walk = the share of random entries that
would reach +k R before -1R, which is 1 / (1 + k).
Uses the Hunt trade file from your Hunt run (results\\lock3\\<file>_hunt.txt).
Usage: py scripts\\mfe_every_trade.py research_2022_25
"""

import bisect
import csv
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars

CAP_BARS = 14 * 1440
LEVELS = (0.5, 1.0, 1.5, 2.0, 3.0, 4.0)


def follow(bars, i, side, entry, stop):
    """Best move in favor, in price, before the stop is hit. Returns (best_move, minutes, stopped)."""
    best = entry
    n = 0
    for bar in bars[i:i + CAP_BARS]:
        if side == "LONG":
            if bar.low <= stop:
                return best - entry, n, True
            best = max(best, bar.high)
        else:
            if bar.high >= stop:
                return entry - best, n, True
            best = min(best, bar.low)
        n += 1
    return abs(best - entry), n, False


def measure(bars, trades):
    times = [b.open_time for b in bars]
    rows = []
    for t in trades:
        entry, stop = float(t["entry"]), float(t["stop"])
        risk = abs(entry - stop)
        i = bisect.bisect_left(times, int(t["entry_time"]))
        move, minutes, stopped = follow(bars, i, t["side"], entry, stop)
        rows.append({
            "entry_time": datetime.fromtimestamp(int(t["entry_time"]) / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "side": t["side"], "weather": t["weather"], "gate": t["gate"], "event": t["event"],
            "entry": entry, "stop": stop, "atr_pct": round(risk / 1.5 / entry * 100, 3),
            "best_R": round(move / risk, 3), "hours_before_stop": round(minutes / 60, 1), "hit_stop": stopped,
            "real_exit": t["exit_reason"], "real_R": t["r_multiple"],
        })
    return rows


def _share(rows, k):
    return f"{sum(r['best_R'] >= k for r in rows) / len(rows):.0%}" if rows else "n/a"


def report(name, rows):
    swing = [r for r in rows if r["weather"] in ("SWING_UP", "SWING_DOWN")]
    chop = [r for r in rows if r["weather"] == "CHOP"]
    print(f"{name}: {len(rows)} Hunt trades, each followed until its own -1R stop (no target, no floors)")
    print(f"  share of trades that reached +R before -1R:   all   swing weather ({len(swing)})   chop weather ({len(chop)})   random walk")
    for k in LEVELS:
        print(f"    +{k:<4}R ({k * 1.5:.2f} ATR)                          {_share(rows, k):>5}   {_share(swing, k):>10}              {_share(chop, k):>8}         {1 / (1 + k):>5.0%}")
    vals = sorted(r["best_R"] for r in rows)
    pick = lambda q: vals[min(len(vals) - 1, int(q * len(vals)))]
    print(f"  best R reached: median {pick(.5):.2f}, 75th {pick(.75):.2f}, 90th {pick(.9):.2f}, 99th {pick(.99):.2f}, max {vals[-1]:.1f}")
    print(f"  still running after 14 days without hitting the stop: {sum(not r['hit_stop'] for r in rows)} trades; median hours to the stop {statistics.median(r['hours_before_stop'] for r in rows if r['hit_stop']):.1f}")


def main():
    name = sys.argv[1]
    text = (ROOT / "results" / "lock3" / f"{name}_hunt.txt").read_text(encoding="utf-8", errors="replace")
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    if not file.is_absolute():
        file = ROOT / file
    trades = list(csv.DictReader(file.open(encoding="utf-8")))
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    rows = measure(bars, trades)
    out = ROOT / "results" / "mfe"
    out.mkdir(parents=True, exist_ok=True)
    with (out / f"{name}_every_trade.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    report(name, rows)
    print(f"  every trade is in {out / (name + '_every_trade.csv')}")


if __name__ == "__main__":
    main()
