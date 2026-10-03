"""Can a swing be told apart in real time? Forward move after each signal. No trades.

Signals, each using only closed bars at the moment it fires:
  first break   first solid 1h close outside the failed-push box
  confirmed     the box says BREAKOUT_CONFIRMED (a second solid close outside, no return inside)
  old swing     the old 4h SWING_UP / SWING_DOWN label, first bar of each run
Forward move is measured after the signal, in the signal's direction, in basis points.
Usage: py scripts\\study_box_breakout.py research_2022_25
"""

import bisect
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.market_structure.failed_push_range import detect_push_range

HORIZONS_H = (8, 16, 32, 64)


def _hunt_module():
    spec = importlib.util.spec_from_file_location("hunt", ROOT / "scripts" / "backtest_desktop_cfi.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _forward(series, i, side, step):
    """Directional move in bp after bar i, for each horizon in hours, on a series with bars of `step` hours."""
    out = []
    for h in HORIZONS_H:
        k = i + h // step
        if k >= len(series):
            out.append(None)
            continue
        move = (series[k].close / series[i].close - 1) * 10_000
        out.append(move if side == "up" else -move)
    return out


def _summary(label, events):
    parts = []
    for n, h in enumerate(HORIZONS_H):
        vals = [e[n] for e in events if e[n] is not None]
        if not vals:
            parts.append(f"{h}h n/a")
            continue
        wins = sum(v > 0 for v in vals) / len(vals)
        parts.append(f"{h}h {sum(vals) / len(vals):+.0f}bp ({wins:.0%})")
    print(f"  {label:<14} n={len(events):<5} " + "  ".join(parts))


def main():
    name = sys.argv[1]
    db = research_db_path(f"backend/{name}.db")
    bars, _ = load_bars(db, "BTC_USDT", None, None)
    analyze(bars, name)


def analyze(bars, name):
    h1 = resample(bars, "1h")
    h4 = resample(bars, "4h")
    print(f"{name} forward move after each signal (direction-adjusted, bp, % positive)")

    first, confirmed = [], []
    prev = None
    for i in range(240, len(h1)):
        state = detect_push_range(h1[i - 239 : i + 1])
        phase = state.phase
        if state.high is not None and phase != prev:
            close = h1[i].close
            side = "up" if close > state.high else ("down" if close < state.low else None)
            if side and phase == "BREAKOUT_CANDIDATE":
                first.append(_forward(h1, i, side, 1))
            if side and phase == "BREAKOUT_CONFIRMED":
                confirmed.append(_forward(h1, i, side, 1))
        prev = phase

    hunt = _hunt_module()
    atrs = hunt._atr(h4)
    old = []
    last = "CHOP"
    h1_close = [b.close_time for b in h1]
    for j in range(24, len(h4) - 1):
        end = bisect.bisect_right(h1_close, h4[j].close_time)
        flag = hunt._weather(h4[: j + 1], h1[max(0, end - 30):end], atrs)
        if flag != last and flag != "CHOP":
            old.append(_forward(h4, j, "up" if flag == "SWING_UP" else "down", 4))
        last = flag

    drift = [_forward(h1, i, "up", 1) for i in range(240, len(h1), 24)]
    _summary("first break", first)
    _summary("confirmed", confirmed)
    _summary("old swing", old)
    _summary("any bar, long", drift)


if __name__ == "__main__":
    main()
