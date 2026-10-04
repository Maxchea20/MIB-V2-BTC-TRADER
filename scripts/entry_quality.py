"""Is the Hunt entry a good entry point? No exits, no fees: after the entry, does price go your way before it goes against you?

Entry score = share of trades that reach +k R before -k R (the same distance each way). A random entry scores 50%.
Same bar touching both sides counts as against you. R = the stop distance of the trade.
Part 1: the score by distance, and by side / event / gate / weather (does the entry type matter?).
Part 2: things you can see at the moment of entry, split into thirds: is the entry better when they are high or low?
  trend 1h / 4h   how far price is above (for a long) or below (for a short) its 20-bar average, in 15m ATR. High = with the trend
  rsi 1h          RSI(14) of the 1h bars, flipped for shorts. High = momentum with you
  volume          last closed 1h volume vs the average of the 24 before it
  room            distance to the 20-bar 4h high (long) or low (short), in R. Low or negative = already breaking out
  stop size       stop distance as % of price (a proxy for volatility)
  hour            UTC hour block
A feature only counts if the same direction shows up in all three files. * marks a spread of 6 points or more.
Uses only bars closed before the entry. Usage: py scripts\\entry_quality.py research_2022_25
"""

import bisect
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample

KS = (0.25, 0.5, 1.0, 2.0)
CAP = 14 * 1440


def outcomes(bars, i, side, entry, risk):
    """For each k: 1 if +k R is reached before -k R, else 0 (a bar touching both counts as against). None if unresolved."""
    res = {k: None for k in KS}
    for bar in bars[i:i + CAP]:
        if side == "LONG":
            fav, adv = (bar.high - entry) / risk, (entry - bar.low) / risk
        else:
            fav, adv = (entry - bar.low) / risk, (bar.high - entry) / risk
        for k in KS:
            if res[k] is None:
                if adv >= k:
                    res[k] = 0
                elif fav >= k:
                    res[k] = 1
        if all(v is not None for v in res.values()):
            break
    return res


def ema(values, n=20):
    out, prev = [], None
    for v in values:
        prev = v if prev is None else prev + (v - prev) * 2 / (n + 1)
        out.append(prev)
    return out


def rsi(values, n=14):
    out = [50.0] * len(values)
    gain = loss = 0.0
    for i in range(1, len(values)):
        d = values[i] - values[i - 1]
        g, l = max(d, 0), max(-d, 0)
        if i <= n:
            gain, loss = gain + g / n, loss + l / n
        else:
            gain, loss = (gain * (n - 1) + g) / n, (loss * (n - 1) + l) / n
        out[i] = 100 - 100 / (1 + gain / loss) if loss else 100.0
    return out


def build(bars, trades):
    h1, h4 = resample(bars, "1h"), resample(bars, "4h")
    c1, c4 = [b.close for b in h1], [b.close for b in h4]
    e1, e4, r1 = ema(c1), ema(c4), rsi(c1)
    t1, t4 = [b.close_time for b in h1], [b.close_time for b in h4]
    times = [b.open_time for b in bars]
    rows = []
    for t in trades:
        entry, stop = float(t["entry"]), float(t["stop"])
        risk = abs(entry - stop)
        sign = 1 if t["side"] == "LONG" else -1
        ts = int(t["entry_time"])
        i = bisect.bisect_left(times, ts)
        a, b = bisect.bisect_right(t1, ts) - 1, bisect.bisect_right(t4, ts) - 1
        if a < 25 or b < 25:
            continue
        atr15 = risk / 1.5
        vol_prev = [x.volume for x in h1[a - 24:a]]
        window = h4[b - 19:b + 1]
        room = ((max(x.high for x in window) - entry) if sign == 1 else (entry - min(x.low for x in window))) / risk
        row = {
            "side": t["side"], "event": t["event"], "gate": t["gate"], "weather": "SWING" if t["weather"] != "CHOP" else "CHOP",
            "trend 1h": sign * (c1[a] - e1[a]) / atr15, "trend 4h": sign * (c4[b] - e4[b]) / atr15,
            "rsi 1h": r1[a] if sign == 1 else 100 - r1[a], "volume": h1[a].volume / (sum(vol_prev) / 24) if sum(vol_prev) else 1.0,
            "room": room, "stop size": risk / entry * 100,
            "hour": f"{datetime.fromtimestamp(ts / 1000, timezone.utc).hour // 4 * 4:02d}-{datetime.fromtimestamp(ts / 1000, timezone.utc).hour // 4 * 4 + 4:02d}h",
        }
        row["out"] = outcomes(bars, i, t["side"], entry, risk)
        rows.append(row)
    return rows


def pct(rows, k=1.0):
    vals = [r["out"][k] for r in rows if r["out"][k] is not None]
    return (sum(vals) / len(vals), len(vals)) if vals else (float("nan"), 0)


def report(name, rows):
    print(f"{name}: {len(rows)} Hunt entries. Share reaching +k R before -k R (random = 50%)")
    print("  " + "   ".join(f"{k:g}R: {pct(rows, k)[0]:.0%}" for k in KS))
    for dim in ("side", "event", "gate", "weather"):
        groups = sorted({r[dim] for r in rows})
        print(f"  {dim:<8} " + "   ".join(f"{g} {pct([r for r in rows if r[dim] == g])[0]:.0%} (n={len([r for r in rows if r[dim] == g])})" for g in groups) + "   [at 1R]")
    print("  thirds of each feature, share reaching +1R first (low / mid / high):")
    for feat in ("trend 1h", "trend 4h", "rsi 1h", "volume", "room", "stop size"):
        ordered = sorted(rows, key=lambda r: r[feat])
        n = len(ordered)
        parts = [ordered[:n // 3], ordered[n // 3:2 * n // 3], ordered[2 * n // 3:]]
        p = [pct(x)[0] for x in parts]
        spread = (p[2] - p[0]) * 100
        print(f"    {feat:<10} {p[0]:.0%} / {p[1]:.0%} / {p[2]:.0%}   spread {spread:+.0f} pts {'*' if abs(spread) >= 6 else ''}   (cuts {parts[0][-1][feat]:.2f} / {parts[1][-1][feat]:.2f})")
    hours = sorted({r["hour"] for r in rows})
    print("    hour       " + "  ".join(f"{h} {pct([r for r in rows if r['hour'] == h])[0]:.0%}" for h in hours))


def main():
    name = sys.argv[1]
    text = (ROOT / "results" / "lock3" / f"{name}_hunt.txt").read_text(encoding="utf-8", errors="replace")
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    if not file.is_absolute():
        file = ROOT / file
    trades = list(csv.DictReader(file.open(encoding="utf-8")))
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    report(name, build(bars, trades))


if __name__ == "__main__":
    main()
