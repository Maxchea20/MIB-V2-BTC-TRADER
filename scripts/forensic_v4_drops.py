"""Forensic of the worst drawdowns in Hunt V4 (Hunt V3 + Floors, fixed box). No new Hunt run.

Rebuilds the Hunt V4 trade list from the saved floors Hunt file (box on closed 1h bars, chop book, one position),
then for the 3 worst drawdowns shows when they happened, what the market was doing, and which trades lost.
Usage: py scripts\\forensic_v4_drops.py research_2022_25
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
HOUR = 3_600_000


def _day(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d")


def _first_year(path):
    with path.open(encoding="utf-8") as handle:
        row = next(csv.DictReader(handle), None)
    return _day(int(row["entry_time"]))[:4] if row else ""


def _norm(t):
    return {
        "book": t.get("book", "HUNT"), "side": t["side"], "entry": float(t["entry"]), "stop": float(t["stop"]),
        "t0": int(t["entry_time"]), "t1": int(t["exit_time"]), "reason": t["exit_reason"], "r": float(t["r_multiple"]),
        "weather": t.get("weather") or "-", "event": t.get("event") or "-",
    }


def _episodes(rows, count=3):
    eq = peak = 0.0
    peak_i = -1
    eps, cur = [], None
    for i, t in enumerate(rows):
        eq += t["r"]
        if eq >= peak:
            if cur:
                eps.append(cur)
            peak, peak_i, cur = eq, i, None
        else:
            if cur is None:
                cur = {"peak_i": peak_i, "depth": 0.0, "trough_i": i}
            if peak - eq > cur["depth"]:
                cur["depth"], cur["trough_i"] = peak - eq, i
    if cur:
        eps.append(cur)
    return sorted(eps, key=lambda e: -e["depth"])[:count]


def _b(trades):
    if not trades:
        return "n=0"
    rs = [t["r"] for t in trades]
    return f"n={len(rs):<4} avg {sum(rs) / len(rs):+.2f}R total {sum(rs):+.1f}R win {sum(r > 0.05 for r in rs) / len(rs):.0%}"


def _context(series, times, t0, t1):
    a = max(0, bisect.bisect_right(times, t0) - 1)
    b = max(a, bisect.bisect_right(times, t1) - 1)
    window = series[a:b + 1]
    closes = [x.close for x in window]
    net = closes[-1] / closes[0] - 1
    path = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
    er = abs(closes[-1] - closes[0]) / path if path else 0.0
    rng = (max(x.high for x in window) - min(x.low for x in window)) / closes[0]
    return net, er, rng


def analyze(name, series, trades):
    trades = sorted(trades, key=lambda t: t["t0"])
    times = [x.open_time for x in series]
    all_r = [t["r"] for t in trades]
    eq = peak = dip = 0.0
    for r in all_r:
        eq += r
        peak = max(peak, eq)
        dip = min(dip, eq - peak)
    atr_pct = sorted(abs(t["entry"] - t["stop"]) / 1.5 / t["entry"] for t in trades if t["book"] == "HUNT")
    median_atr = atr_pct[len(atr_pct) // 2]
    print(f"{name} Hunt V4 rebuilt: n={len(trades)} {sum(all_r) / len(all_r):+.3f}R total {sum(all_r):+.0f}R dip {dip:.1f}R")
    eps = _episodes(trades)
    print("  3 worst drawdowns:  from -> to   depth  trades days  BTC move  trend(0-1)  vol x median  long/short avg R  Hunt/chop avg R")
    for k, e in enumerate(eps, 1):
        w = trades[e["peak_i"] + 1:e["trough_i"] + 1]
        net, er, rng = _context(series, times, w[0]["t0"], w[-1]["t1"])
        hunt = [t for t in w if t["book"] == "HUNT"]
        vol = (sum(abs(t["entry"] - t["stop"]) / 1.5 / t["entry"] for t in hunt) / len(hunt)) / median_atr if hunt else 0
        avg = lambda xs: sum(t["r"] for t in xs) / len(xs) if xs else float("nan")
        print(
            f"   {k}. {_day(w[0]['t0'])} -> {_day(w[-1]['t1'])}  -{e['depth']:.1f}R  {len(w):<4} {(w[-1]['t1'] - w[0]['t0']) / 86_400_000:>4.0f}  "
            f"{net:+.1%}   {er:.2f}   {vol:.2f}x   {avg([t for t in w if t['side'] == 'LONG']):+.2f}/{avg([t for t in w if t['side'] == 'SHORT']):+.2f}   "
            f"{avg(hunt):+.2f}/{avg([t for t in w if t['book'] == 'CHOP']):+.2f}"
        )
    e = eps[0]
    w = trades[e["peak_i"] + 1:e["trough_i"] + 1]
    print(f"  worst drawdown in detail ({_day(w[0]['t0'])} -> {_day(w[-1]['t1'])}), window vs the whole file:")

    def line(label, pick):
        sub_w = [t for t in w if pick(t)]
        sub_a = [t for t in trades if pick(t)]
        print(f"    {label:<14} {_b(sub_w)}   | file: avg {sum(t['r'] for t in sub_a) / len(sub_a):+.2f}R" if sub_a else f"    {label:<14} n=0")

    line("all", lambda t: True)
    for book in ("HUNT", "CHOP"):
        line("book " + book, lambda t, book=book: t["book"] == book)
    for side in ("LONG", "SHORT"):
        line(side, lambda t, side=side: t["side"] == side)
    for reason in sorted({t["reason"] for t in w}):
        line("exit " + reason, lambda t, reason=reason: t["reason"] == reason)
    for weather in ("SWING_UP", "SWING_DOWN", "CHOP"):
        line("weather " + weather, lambda t, weather=weather: t["weather"] == weather)
    buckets = {}
    for t in w:
        buckets.setdefault(datetime.fromtimestamp(t["t0"] / 1000, timezone.utc).hour // 4 * 4, []).append(t["r"])
    worst = sorted(buckets.items(), key=lambda kv: sum(kv[1]))[:2]
    print("    worst entry hours (UTC): " + ", ".join(f"{h:02d}-{h + 4:02d}h {sum(v):+.1f}R over {len(v)}" for h, v in worst))


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
    merged = hc._one_position(kept, hc._chop(series, active))
    analyze(f"{name} ({files[-1].parent.name})", series, [_norm(t) for t in merged])


if __name__ == "__main__":
    main()
