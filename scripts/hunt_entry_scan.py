"""Which Hunt entries are better? Real fill only. Runs the Hunt engine with floors + realfill (market order at the next 1m open after the 5m signal closes),
then splits every trade by things you can know AT THE SIGNAL (no future): hour, weekday, side, gate, event, weather, slot in the 15m bar, how far the 5m close is past the level (ext, in ATR),
volatility, 4h momentum with/against the trade, last-4h move, where the level sits in the last 24h range.
Two columns per bucket:
  A  the engine's own exit (stop 1.5 / target 2.5 x 15m ATR, floors)        -> what Hunt really does
  B  swing-size exit on the same entries (stop 2.0 x 4h ATR, target 4R, plain) -> the exit that worked in the MTF tests
A bucket only means something if it is better than ALL on every file. Run it on the three files and compare.
Usage: py scripts\\hunt_entry_scan.py research_binance
"""

import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.setups import hunt_exits

import backtest_desktop_cfi as eng

FIVE, FIFTEEN = eng.FIVE, eng.FIFTEEN
NONE = dict(tiers=())


def rows_for(bars, trades):
    b5, b15, b1, b4 = (resample(bars, x) for x in ("5m", "15m", "1h", "4h"))
    by5 = {b.open_time: b for b in b5}
    atr15, atr4 = eng._atr(b15), eng._atr(b4)
    end = bars[-1].open_time + 60_000
    out = []
    for t in trades:
        ts = int(t["entry_time"])
        sign = 1 if t["side"] == "LONG" else -1
        entry = float(t["entry"])
        o5 = ts - FIVE
        start = o5 // FIFTEEN * FIFTEEN
        j15 = eng._closed(b15, start, FIFTEEN)
        j4 = eng._closed(b4, ts, 14_400_000)
        j1 = eng._closed(b1, ts, 3_600_000)
        if j15 < 100 or j4 < 22 or j1 < 6 or not atr15[j15 - 1] or not atr4[j4 - 1] or o5 not in by5:
            continue
        a15, a4 = atr15[j15 - 1], atr4[j4 - 1]
        level = b15[j15 - 1].high if sign == 1 else b15[j15 - 1].low
        win = b15[j15 - 96:j15]
        hi, lo = max(b.high for b in win), min(b.low for b in win)
        when = datetime.fromtimestamp(ts / 1000, timezone.utc)
        f = {
            "hour": when.hour,
            "weekend": when.weekday() >= 5,
            "side": t["side"],
            "gate": t["gate"],
            "event": t["event"],
            "weather": t["weather"],
            "slot": (o5 - start) // FIVE + 1,
            "ext": sign * (by5[o5].close - level) / a15,
            "atr_pct": a15 / entry * 100,
            "mom4": sign * (b4[j4 - 1].close - b4[j4 - 21].close) / a4,
            "ret4h": sign * (b1[j1 - 1].close - b1[j1 - 5].close) / a4,
            "pos24": ((level - lo) if sign == 1 else (hi - level)) / (hi - lo) if hi > lo else 0.5,
        }
        risk = 2.0 * a4
        tr = {"side": t["side"], "atr": a4, "entry": entry, "stop": entry - sign * risk, "target": entry + sign * 4 * risk, "risk": risk}
        done = hunt_exits.walk(tr, bars, ts, end, NONE) or hunt_exits._close(tr, bars[-1].close, bars[-1].open_time, "END")
        out.append((f, float(t["r_multiple"]), done["r_multiple"]))
    return out


def buckets():
    def rng(key, edges, labels):
        return [(key, lab, (lambda f, k=key, lo=lo, hi=hi: lo <= f[k] < hi)) for lab, (lo, hi) in zip(labels, edges)]
    big = 1e9
    b = []
    b += rng("hour", [(0, 4), (4, 8), (8, 12), (12, 16), (16, 20), (20, 24)], ["00-04 UTC", "04-08", "08-12", "12-16", "16-20", "20-24"])
    b += [("weekend", "weekday", lambda f: not f["weekend"]), ("weekend", "weekend", lambda f: f["weekend"])]
    for key in ("side", "gate", "event", "weather"):
        vals = {"side": ("LONG", "SHORT"), "gate": ("cfast", "internal", "rearm"), "event": ("BOS", "CHoCH"), "weather": ("SWING_UP", "SWING_DOWN", "CHOP")}[key]
        b += [(key, v, (lambda f, k=key, v=v: f[k] == v)) for v in vals]
    b += rng("slot", [(1, 2), (2, 3), (3, 4)], ["slot 1 (first 5m)", "slot 2", "slot 3 (15m close)"])
    b += rng("ext", [(-big, 0.15), (0.15, 0.4), (0.4, 0.8), (0.8, big)], ["ext <0.15 ATR", "0.15-0.4", "0.4-0.8", ">0.8 ATR"])
    b += rng("atr_pct", [(0, 0.2), (0.2, 0.3), (0.3, 0.45), (0.45, big)], ["15m ATR <0.20%", "0.20-0.30%", "0.30-0.45%", ">0.45%"])
    b += rng("mom4", [(-big, -1), (-1, 1), (1, big)], ["4h momentum against (<-1 ATR)", "flat (-1..1)", "with the trade (>1)"])
    b += rng("ret4h", [(-big, -0.5), (-0.5, 0.5), (0.5, big)], ["last 4h against (<-0.5)", "flat", "with the trade (>0.5)"])
    b += rng("pos24", [(0, 0.5), (0.5, 0.9), (0.9, 1.01)], ["level mid 24h range (<0.5)", "upper 0.5-0.9", "at the 24h extreme (>0.9)"])
    return b


def line(rows):
    n = len(rows)
    if not n:
        return None
    a = [r[1] for r in rows]
    bb = [r[2] for r in rows]
    return n, sum(x > 0 for x in a) / n, sum(a) / n, sum(bb) / n


def trades_for(name):
    """Real-fill Hunt trades (floors, realfill) for a research file. The engine run is cached: results\\hunt_realfill_<name>.path"""
    cache = ROOT / "results" / f"hunt_realfill_{name}.path"
    if cache.exists():
        file = Path(cache.read_text().strip())
        if file.exists():
            return list(csv.DictReader(file.open(encoding="utf-8")))
    cmd = [sys.executable, str(ROOT / "scripts" / "backtest_desktop_cfi.py"), f"backend/{name}.db", "floors", "realfill"]
    text = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, check=True).stdout
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(str(file))
    return list(csv.DictReader(file.open(encoding="utf-8")))


def main():
    name = sys.argv[1]
    trades = trades_for(name)
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    rows = rows_for(bars, trades)
    n, w, a, b = line(rows)
    print(f"{name}: {n} real-fill Hunt trades.  A = engine exit (1.5/2.5 x 15m ATR + floors)   B = 2.0 x 4h ATR stop, 4R target, same entries")
    print(f"  {'ALL':<42}{n:5d}  win {w:4.0%}  A {a:+.3f}R   B {b:+.3f}R")
    last = None
    for key, label, pred in buckets():
        got = line([r for r in rows if pred(r[0])])
        if key != last:
            print(f"  [{key}]")
            last = key
        if got and got[0] >= 30:
            n2, w2, a2, b2 = got
            print(f"  {label:<42}{n2:5d}  win {w2:4.0%}  A {a2:+.3f}R   B {b2:+.3f}R")


if __name__ == "__main__":
    main()
