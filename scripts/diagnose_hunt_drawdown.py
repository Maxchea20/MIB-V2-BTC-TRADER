"""Hunt alone with floors: where is the drawdown, and what cuts it without the chop book? No new Hunt run.

Reads the newest `floors` Hunt trade file for the period (run scripts\\run_floor_v3.py or
`py scripts\\backtest_desktop_cfi.py backend\\<file>.db floors` first). Prints:
  A all trades, B outside the failed-push box (Hunt V3's Hunt book, no chop), C inside the box
  the 3 worst drawdowns, loss clustering, and three risk rules tried on A and B:
    day cap     no new trade for the rest of the UTC day once the day is down 3R
    pause       after 4 losses in a row, skip trades for 12 hours
    throttle    half size while the equity is 10R or more below its peak
  and on A only: box half (trades inside the box at half size) and box half + throttle
Usage: py scripts\\diagnose_hunt_drawdown.py research_2022_25
"""

import bisect
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
DAY = 86_400_000


def _stats(rs):
    if not rs:
        return "n=0"
    eq = peak = dip = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dip = min(dip, eq - peak)
    total = sum(rs)
    return f"n={len(rs)} {total / len(rs):+.3f}R total={total:+.0f}R dip={dip:.1f}R R/dip={total / abs(dip) if dip else 0:.1f}"


def _day(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d")


def _worst(rows, count=3):
    eq = peak = 0.0
    peak_i = 0
    episodes, cur = [], None
    for i, (t, r) in enumerate(rows):
        eq += r
        if eq >= peak:
            if cur:
                episodes.append(cur)
            peak, peak_i, cur = eq, i, None
        else:
            if cur is None:
                cur = {"peak_i": peak_i, "depth": 0.0, "trough_i": i}
            if peak - eq > cur["depth"]:
                cur["depth"], cur["trough_i"] = peak - eq, i
    if cur:
        episodes.append(cur)
    out = []
    for e in sorted(episodes, key=lambda x: -x["depth"])[:count]:
        a, b = rows[e["peak_i"]][0], rows[e["trough_i"]][0]
        out.append(f"{_day(a)} to {_day(b)}  -{e['depth']:.1f}R over {e['trough_i'] - e['peak_i']} trades")
    return out


def _day_cap(rows, cap=3.0):
    pnl, out = {}, []
    for t, r in rows:
        d = t // DAY
        if pnl.get(d, 0.0) <= -cap:
            continue
        pnl[d] = pnl.get(d, 0.0) + r
        out.append(r)
    return out


def _pause(rows, streak_n=4, hours=12):
    out, streak, until = [], 0, 0
    for t, r in rows:
        if t < until:
            continue
        out.append(r)
        streak = streak + 1 if r < 0 else 0
        if streak >= streak_n:
            until, streak = t + hours * 3_600_000, 0
    return out


def _throttle(rows, depth=10.0, size=0.5):
    eq = peak = 0.0
    out = []
    for t, r in rows:
        k = size if peak - eq >= depth else 1.0
        eq += r * k
        peak = max(peak, eq)
        out.append(r * k)
    return out


def main():
    name = sys.argv[1]
    folder = ROOT / "results" / "exp-hunt-desktop-cfi-floors"
    files = [f for f in sorted(folder.glob("*/trades.csv")) if _first_year(f) == YEAR[name]]
    if not files:
        raise SystemExit("no floors trade file for this period. Run: py scripts\\run_floor_v3.py " + name + " floors")
    trades = list(csv.DictReader(files[-1].open(encoding="utf-8")))
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    import backtest_hunt_chop as hc
    active = hc._flags(resample(bars, "1h"))
    keys = sorted(active)

    def in_box(ts):
        i = bisect.bisect_right(keys, ts)
        return bool(i and active[keys[i - 1]] is not None)

    rows = [(int(t["entry_time"]), float(t["r_multiple"]), in_box(int(t["entry_time"]))) for t in trades]
    rows.sort()
    a = [(t, r) for t, r, _ in rows]
    b = [(t, r) for t, r, box in rows if not box]
    c = [(t, r) for t, r, box in rows if box]
    print(f"{name} Hunt alone with floors ({files[-1].parent.name})")
    print("  A all trades      " + _stats([r for _, r in a]))
    print("  B outside the box " + _stats([r for _, r in b]) + "   (Hunt V3's Hunt book, no chop)")
    print("  C inside the box  " + _stats([r for _, r in c]))
    print("  3 worst drawdowns in A:")
    for line in _worst(a):
        print("    " + line)
    losses = [r < 0 for _, r in a]
    after3 = [losses[i] for i in range(3, len(losses)) if all(losses[i - 3:i])]
    print(f"  loss clustering: {sum(losses) / len(losses):.0%} of trades lose; after 3 losses in a row {sum(after3) / len(after3):.0%} lose (n={len(after3)})")
    half = [(t, r * (0.5 if box else 1.0)) for t, r, box in rows]
    for label, rows_ in (("A", a), ("B", b)):
        print(f"  risk rules on {label}:")
        print("    none      " + _stats([r for _, r in rows_]))
        print("    day cap   " + _stats(_day_cap(rows_)))
        print("    pause     " + _stats(_pause(rows_)))
        print("    throttle  " + _stats(_throttle(rows_)))
        if label == "A":
            print("    box half  " + _stats([r for _, r in half]))
            print("    box half + throttle " + _stats(_throttle(half)))


def _first_year(path):
    with path.open(encoding="utf-8") as handle:
        row = next(csv.DictReader(handle), None)
    return _day(int(row["entry_time"]))[:4] if row else ""


if __name__ == "__main__":
    main()
