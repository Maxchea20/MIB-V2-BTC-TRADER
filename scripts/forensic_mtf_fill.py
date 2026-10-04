"""Lock 1 (4h trend, 1h break, 15m break): fake fill vs real fill, signal by signal.
Every 15m close beyond the level is one signal. All signals are kept (no one-position rule) so the two fills can be compared on the SAME signal.
  fake   the old fill: the level, booked inside the bar that has already closed (not tradable)
  real   the first 1m open after the 15m bar closes
1) Why so few trades: the filter funnel and how long trades hold (a trade that holds days blocks every signal until it exits).
2) The fill gap: how far the real entry is from the fake one, in R and in % of price.
3) Each signal is one of:  both win | LATE (fake wins, real loses: the entry gap or the run was missed) | FAILED (both lose: the breakout reversed) | real only wins
4) Retest: after the close, does price come back to the level? A limit order at the level, waiting 1h / 4h / 24h, for the signals that DO come back vs the ones that run away.
Usage: py scripts\\forensic_mtf_fill.py exp-mtf-nextopen-15m [backend\\research_2022_25.db]     (also exp-mtf-nextopen-4h-2R)
"""

import bisect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.setups.hunt_lookback import _simulate
from btc_research.setups.mtf_stack import run_mtf

WAITS = ((60, "1h"), (240, "4h"), (1440, "24h"))


def avg(xs):
    return f"{sum(xs) / len(xs):+.3f}R" if xs else "-"


def analyze(bars, cfg):
    b15, b1h, b4h = (resample(bars, x) for x in ("15m", "1h", "4h"))
    both = ["LONG", "SHORT"]
    every = dict(cfg, quiet_minutes=-10**9)
    fake, _ = run_mtf(bars, b15, b1h, b4h, dict(every, fill_mode="legacy"), both)
    real, _ = run_mtf(bars, b15, b1h, b4h, dict(every, fill_mode="next_open"), both)
    one, skips = run_mtf(bars, b15, b1h, b4h, dict(cfg, fill_mode="next_open"), both)
    f = {t["decision_time"]: t for t in fake}
    r = {t["decision_time"]: t for t in real}
    keys = sorted(set(f) & set(r))
    print(f"\n1) WHY SO FEW TRADES")
    print(f"   15m bars {len(b15)}; skipped because: " + ", ".join(f"{k} {v}" for k, v in sorted(skips.items(), key=lambda kv: -kv[1])))
    print(f"   signals (every 15m close beyond the level, overlapping allowed): {len(real)}")
    holds = [t["hold_seconds"] / 3600 for t in one]
    busy = sum(t["hold_seconds"] for t in one) / ((bars[-1].open_time - bars[0].open_time) / 1000)
    print(f"   trades taken with one position at a time: {len(one)}; average hold {sum(holds) / max(1, len(holds)):.1f}h; in a trade {busy:.0%} of the time")
    gaps, pct = [], []
    cat = {"both win": [], "LATE (fake wins, real loses)": [], "FAILED (both lose)": [], "real only wins": []}
    for k in keys:
        a, b = f[k], r[k]
        sign = 1 if b["side"] == "LONG" else -1
        risk = abs(b["entry"] - b["stop"])
        g = (b["entry"] - a["entry"]) * sign / risk
        gaps.append(g)
        pct.append((b["entry"] - a["entry"]) * sign / a["entry"] * 100)
        w1, w2 = a["r_multiple"] > 0, b["r_multiple"] > 0
        cat["both win" if w1 and w2 else "LATE (fake wins, real loses)" if w1 else "real only wins" if w2 else "FAILED (both lose)"].append((g, a["r_multiple"], b["r_multiple"]))
    n = len(keys)
    gs = sorted(gaps)
    q = lambda p: gs[min(n - 1, int(p * n))]
    print(f"\n2) FILL GAP on {n} signals (real entry minus fake entry, + = worse for you)")
    print(f"   in R: median {q(.5):+.2f}  75th {q(.75):+.2f}  90th {q(.9):+.2f};  in % of price: median {sorted(pct)[n // 2]:+.3f}%")
    print(f"   fake fill all signals {avg([f[k]['r_multiple'] for k in keys])}   real fill all signals {avg([r[k]['r_multiple'] for k in keys])}")
    print("\n3) WHAT HAPPENED TO EACH SIGNAL")
    for name, rows in cat.items():
        print(f"   {name:<30} {len(rows):5d} ({len(rows) / n:.0%})  avg gap {avg([x[0] for x in rows])}  fake R {avg([x[1] for x in rows])}  real R {avg([x[2] for x in rows])}")
    times = [b.open_time for b in bars]
    print("\n4) DOES PRICE COME BACK TO THE LEVEL? limit order at the level after the 15m close")
    for minutes, label in WAITS:
        back, away = [], []
        for k in keys:
            t = r[k]
            side, level = t["side"], t["thesis_level"]
            risk = abs(t["entry"] - t["stop"])
            i0 = bisect.bisect_left(times, k)
            hit = None
            for j in range(i0, min(len(bars), i0 + minutes)):
                if (bars[j].low <= level) if side == "LONG" else (bars[j].high >= level):
                    hit = j
                    break
            if hit is None:
                away.append(f[k]["r_multiple"])
                continue
            sign = 1 if side == "LONG" else -1
            entry = level
            tgt = abs(t["target"] - t["entry"])
            tr = _simulate(bars, hit, side, entry, entry - sign * risk, entry + sign * tgt, risk, cfg)
            back.append(tr["r_multiple"])
        m = len(back) + len(away)
        print(f"   wait {label:>3}: comes back {len(back)} ({len(back) / m:.0%}) -> limit at the level makes {avg(back)};  runs away {len(away)} ({len(away) / m:.0%}) -> the fake fill claimed {avg(away)} on those")


def main():
    cfg = json.loads((ROOT / "config" / "experiments" / f"{sys.argv[1]}.json").read_text())
    db = research_db_path(sys.argv[2] if len(sys.argv) > 2 else None)
    bars, _ = load_bars(db, cfg.get("symbol") or "BTCUSDT", None, None)
    print(f"{sys.argv[1]} on {db.name}: 1m bars {len(bars)}, stop {cfg['sl_atr']} x {cfg.get('atr_tf', '15m')} ATR, target {cfg['tp_atr']} x ATR")
    analyze(bars, cfg)


if __name__ == "__main__":
    main()
