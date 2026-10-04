"""What did the losing trades do inside the Hunt V4 drops? Hunt: did they get close to TP and U-turn? Chop: where did they enter in the box?

Rebuilds Hunt V4 (saved floors Hunt file, fixed box, chop book, one position) and takes the 3 worst drawdowns.
Hunt: for stopped trades, the best price reached before the stop, in ATR (stop = 1.5 ATR, TP = 2.5 ATR, floor from 1.75 ATR).
Chop: position at entry inside the box (0 = at the line it entered from, 1 = at the far line = the target), how far toward
the target the trade got before it was stopped, box width, and how long it was held. Compared with the rest of the file.
Usage: py scripts\\forensic_v4_paths.py research_2022_25
"""

import bisect
import csv
import statistics
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


def _episodes(trades, count=3):
    eq = peak = 0.0
    peak_i = -1
    eps, cur = [], None
    for i, t in enumerate(trades):
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


def _path(bars, times, t):
    """Best move in favor and worst move against, in price, from entry to the exit bar (exit bar left out)."""
    a = bisect.bisect_left(times, t["t0"])
    b = bisect.bisect_left(times, t["t1"])
    window = bars[a:max(b, a + 1)]
    if t["side"] == "LONG":
        return max(x.high for x in window) - t["entry"], t["entry"] - min(x.low for x in window)
    return t["entry"] - min(x.low for x in window), max(x.high for x in window) - t["entry"]


def _pct(n, d):
    return f"{n / d:.0%}" if d else "n/a"


def _med(vals, fmt="{:.2f}"):
    return fmt.format(statistics.median(vals)) if vals else "n/a"


def hunt_lines(label, trades):
    stops = [t for t in trades if t["book"] == "HUNT" and t["reason"] == "STOP"]
    hunt = [t for t in trades if t["book"] == "HUNT"]
    mfe = [t["mfe"] / t["atr"] for t in stops]
    return (
        f"    {label:<8} Hunt n={len(hunt):<5} TP {_pct(sum(t['reason'] == 'TARGET' for t in hunt), len(hunt)):>4}  floor {_pct(sum(t['reason'] == 'FLOOR' for t in hunt), len(hunt)):>4}  "
        f"stop {_pct(len(stops), len(hunt)):>4} | of the stops: median best {_med(mfe)} ATR, "
        f"never +0.5 ATR {_pct(sum(m < 0.5 for m in mfe), len(mfe))}, got +1.0 ATR {_pct(sum(m >= 1.0 for m in mfe), len(mfe))}, got +1.5 ATR {_pct(sum(m >= 1.5 for m in mfe), len(mfe))}"
    )


def chop_lines(label, trades):
    chop = [t for t in trades if t["book"] == "CHOP"]
    if not chop:
        return f"    {label:<8} Chop n=0"
    pos = [t["pos"] for t in chop]
    stops = [t for t in chop if t["reason"] == "STOP"]
    prog = [t["progress"] for t in stops]
    return (
        f"    {label:<8} Chop n={len(chop):<4} win {_pct(sum(t['r'] > 0 for t in chop), len(chop)):>4} | entry position median {_med(pos)} (0 = at its line, 1 = far line), "
        f"in the middle 0.25-0.75: {_pct(sum(0.25 <= p <= 0.75 for p in pos), len(pos))} | box width {_med([t['width'] * 100 for t in chop], '{:.2f}')}% , stop distance {_med([t['riskpct'] * 100 for t in chop], '{:.2f}')}% | "
        f"stopped: got halfway to target {_pct(sum(p >= 0.5 for p in prog), len(prog))}, held {_med([t['hours'] for t in stops], '{:.0f}')}h"
    )


def analyze(name, bars, trades):
    trades = sorted(trades, key=lambda t: t["t0"])
    times = [b.open_time for b in bars]
    for t in trades:
        fav, _ = _path(bars, times, t)
        t["mfe"] = fav
        t["hours"] = (t["t1"] - t["t0"]) / HOUR
        if t["book"] == "CHOP":
            width = t["line_high"] - t["line_low"]
            far = t["line_high"] if t["side"] == "LONG" else t["line_low"]
            t["pos"] = ((t["entry"] - t["line_low"]) if t["side"] == "LONG" else (t["line_high"] - t["entry"])) / width
            t["progress"] = fav / abs(far - t["entry"]) if far != t["entry"] else 0.0
            t["width"] = width / t["entry"]
            t["riskpct"] = abs(t["entry"] - t["stop"]) / t["entry"]
    print(f"{name}: how the trades in the 3 worst drops behaved, compared with the rest of the file")
    for k, e in enumerate(_episodes(trades), 1):
        w = trades[e["peak_i"] + 1:e["trough_i"] + 1]
        rest = trades[:e["peak_i"] + 1] + trades[e["trough_i"] + 1:]
        print(f"  drop {k}: {_day(w[0]['t0'])} to {_day(w[-1]['t1'])}  -{e['depth']:.1f}R")
        print(hunt_lines("in drop", w))
        print(hunt_lines("rest", rest))
        print(chop_lines("in drop", w))
        print(chop_lines("rest", rest))


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
    trades = []
    for t in merged:
        row = {"book": t["book"], "side": t["side"], "entry": float(t["entry"]), "stop": float(t["stop"]), "t0": int(t["entry_time"]), "t1": int(t["exit_time"]),
               "reason": t["exit_reason"], "r": float(t["r_multiple"])}
        row["atr"] = abs(row["entry"] - row["stop"]) / 1.5
        if t["book"] == "CHOP":
            row["line_high"], row["line_low"] = float(t["line_high"]), float(t["line_low"])
        trades.append(row)
    analyze(f"{name} ({files[-1].parent.name})", bars, trades)


if __name__ == "__main__":
    main()
