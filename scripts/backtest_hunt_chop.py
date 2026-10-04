"""Hunt off while the failed-push box is on. Chop owns that box. One position."""

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
from btc_research.market_structure.failed_push_range import detect_push_range

FIELDS = ("book", "side", "entry", "stop", "target", "exit", "entry_time", "exit_time", "exit_reason", "r_multiple", "net_pnl")


def main():
    db = research_db_path(sys.argv[1] if len(sys.argv) > 1 else None)
    hunt_file = Path(sys.argv[2]) if len(sys.argv) > 2 else sorted((ROOT / "results" / "exp-hunt-desktop-cfi-v1").glob("*/trades.csv"))[-1]
    hunt = list(csv.DictReader(hunt_file.open(encoding="utf-8")))
    hours = next((a.split("=")[1] for a in sys.argv[3:] if a.startswith("hunt-hours=")), None)
    if hours:
        start, end = (int(x) for x in hours.split("-"))
        hunt = [t for t in hunt if start <= datetime.fromtimestamp(int(t["entry_time"]) / 1000, timezone.utc).hour < end]
    swing_only = "swing-only" in sys.argv[3:]
    if swing_only:
        hunt = [t for t in hunt if t["weather"] in ("SWING_UP", "SWING_DOWN")]
    bars, info = load_bars(db, "BTC_USDT", None, None)
    series = resample(bars, "1h")
    print(f"{db.name} 1h={len(series)} hunt={hunt_file}")
    active = _flags(series)
    chop = _chop(series, active)
    kept = [t for t in hunt if not _on(int(t["entry_time"]), active)]
    for trade in kept:
        trade["book"] = "HUNT"
    merged = _one_position(kept, chop)
    if "breakout" in sys.argv[3:]:
        tests = {}
        for mode in ("atr", "line", "trail"):
            brk = _breakouts(series, chop, mode)
            tests[mode] = {"breakout_alone": _bucket(brk), "combined": _bucket(_one_position(kept, chop + brk))}
        print(json.dumps({"db": db.name, "hunt_file": str(hunt_file), "base": _bucket(merged), "breakout_tests": tests}, indent=2))
        return
    folder = ROOT / "results" / ("exp-hunt-chop-swing" if swing_only else ("exp-hunt-chop-hours" if hours else "exp-hunt-chop-arbiter")) / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "trades.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merged)
    print(json.dumps({
        "db": db.name,
        "hunt_file": str(hunt_file),
        "swing_only": swing_only,
        "hunt_hours": hours,
        "hunt": _bucket(hunt),
        "hunt_outside_box": _bucket(kept),
        "chop": _bucket(chop),
        "one_position": _bucket(merged),
        "file": str(folder / "trades.csv"),
    }, indent=2))


def _atr(series, i):
    if i < 15:
        return None
    acc = 0.0
    prev = series[i - 14].close
    for bar in series[i - 13 : i + 1]:
        acc += max(bar.high - bar.low, abs(bar.high - prev), abs(bar.low - prev))
        prev = bar.close
    return acc / 14


def _breakouts(series, chop, mode):
    """After a chop stop (a close through the line), trade the break in that direction. Entry at the next 1h open."""
    index = {b.open_time: i for i, b in enumerate(series)}
    out = []
    for t in chop:
        if t["exit_reason"] != "STOP" or t["exit_time"] not in index:
            continue
        i = index[t["exit_time"]]
        if i + 1 >= len(series):
            continue
        nxt = series[i + 1]
        side = "SHORT" if t["side"] == "LONG" else "LONG"
        sign = 1 if side == "LONG" else -1
        entry = nxt.open + sign * (0.1 + nxt.open * 0.00005)
        line = t["line_low"] if t["side"] == "LONG" else t["line_high"]
        if mode == "atr":
            atr = _atr(series, i)
            if not atr:
                continue
            risk = 1.5 * atr
            stop, target = entry - sign * risk, entry + sign * 2.5 * atr
        else:
            risk = (entry - line) * sign
            if risk <= 0:
                continue
            stop, target = line, (entry + sign * 2 * risk if mode == "line" else None)
        trade = {"book": "BRK", "side": side, "entry": entry, "stop": stop, "target": target, "risk": risk, "entry_time": nxt.open_time}
        done = _walk_break(trade, series, i + 1, mode, sign)
        if done:
            out.append(done)
    return out


def _walk_break(trade, series, start, mode, sign):
    entry, risk, best = trade["entry"], trade["risk"], trade["entry"]
    stop = trade["stop"]
    for bar in series[start : start + 7 * 24]:
        if mode == "atr":
            stopped = bar.low <= stop if sign == 1 else bar.high >= stop
        elif mode == "line":
            stopped = bar.close < stop if sign == 1 else bar.close > stop
        else:
            stopped = bar.low <= stop if sign == 1 else bar.high >= stop
        target = trade["target"]
        got = target is not None and (bar.high >= target if sign == 1 else bar.low <= target)
        if stopped or got:
            price = stop if stopped else target
            reason = "STOP" if stopped else "TARGET"
            return _close_break(trade, price, bar.open_time, reason)
        if mode == "trail":
            best = max(best, bar.high) if sign == 1 else min(best, bar.low)
            stop = max(trade["stop"], best - risk) if sign == 1 else min(trade["stop"], best + risk)
    return None


def _close_break(trade, price, exit_time, reason):
    gross = (price - trade["entry"]) * (1 if trade["side"] == "LONG" else -1)
    net = gross - (trade["entry"] + price) * 0.0002
    trade.update({"exit": price, "exit_time": exit_time, "exit_reason": reason, "net_pnl": net, "r_multiple": net / trade["risk"]})
    return trade


def _flags(series):
    out = {}
    for i in range(240, len(series)):
        state = detect_push_range(series[i - 239 : i + 1])
        out[series[i].open_time] = state if state.active and state.phase == "RANGE" else None
    return out


def _chop(series, active):
    trades = []
    quiet_until = 0
    for i in range(240, len(series) - 1):
        bar = series[i]
        state = active.get(bar.open_time)
        if bar.open_time < quiet_until or state is None or state.high is None:
            continue
        width = state.high - state.low
        if width <= 0:
            continue
        side = _reject(bar, state.high, state.low, width)
        if not side:
            continue
        nxt = series[i + 1]
        slip = 0.1 + nxt.open * 0.00005
        entry = nxt.open + slip if side == "LONG" else nxt.open - slip
        stop = state.low if side == "LONG" else state.high
        target = state.high if side == "LONG" else state.low
        risk = abs(entry - stop)
        if side == "LONG" and (stop >= entry or target <= entry):
            continue
        if side == "SHORT" and (stop <= entry or target >= entry):
            continue
        trade = {"book": "CHOP", "side": side, "entry": entry, "stop": stop, "target": target, "risk": risk, "entry_time": nxt.open_time, "line_high": state.high, "line_low": state.low}
        done = _walk(trade, series, i + 1)
        if not done:
            continue
        trades.append(done)
        quiet_until = done["exit_time"]
    return trades


def _reject(bar, high, low, width):
    if (bar.low < low and low < bar.close <= high and bar.close > bar.open) or (bar.low >= low and bar.close <= low + 0.25 * width and bar.close > bar.open):
        return "LONG"
    if (bar.high > high and low <= bar.close < high and bar.close < bar.open) or (bar.high <= high and bar.close >= high - 0.25 * width and bar.close < bar.open):
        return "SHORT"
    return None


def _walk(trade, series, start):
    for bar in series[start:]:
        broke = bar.close < trade["line_low"] if trade["side"] == "LONG" else bar.close > trade["line_high"]
        target_hit = bar.high >= trade["target"] if trade["side"] == "LONG" else bar.low <= trade["target"]
        if not broke and not target_hit:
            continue
        price = trade["stop"] if broke else trade["target"]
        gross = price - trade["entry"] if trade["side"] == "LONG" else trade["entry"] - price
        trade["exit"] = price
        trade["exit_time"] = bar.open_time
        trade["exit_reason"] = "STOP" if broke else "TARGET"
        trade["net_pnl"] = trade["net_pnl"] if "net_pnl" in trade and trade.get("book") == "HUNT" else gross - (trade["entry"] + price) * 0.0002
        trade["r_multiple"] = trade["net_pnl"] / trade["risk"] if trade.get("book") != "HUNT" else float(trade["r_multiple"])
        return trade
    return None


def _one_position(hunt, chop):
    rows = sorted(hunt + chop, key=lambda t: int(t["entry_time"]))
    out = []
    quiet = 0
    for trade in rows:
        if int(trade["entry_time"]) < quiet:
            continue
        out.append(trade)
        quiet = int(trade["exit_time"])
    return out


def _on(ts, active):
    keys = sorted(active)
    lo, hi = 0, len(keys)
    while lo < hi:
        mid = (lo + hi) // 2
        if keys[mid] <= ts:
            lo = mid + 1
        else:
            hi = mid
    return bool(lo and active[keys[lo - 1]] is not None)


def _bucket(rows):
    if not rows:
        return {"n": 0}
    equity = peak = dip = 0.0
    for trade in rows:
        equity += float(trade["r_multiple"])
        peak = max(peak, equity)
        dip = min(dip, equity - peak)
    return {
        "n": len(rows),
        "expectancy_r": round(sum(float(t["r_multiple"]) for t in rows) / len(rows), 4),
        "drawdown_r": round(dip, 2),
        "hunt": sum(t.get("book", "HUNT") == "HUNT" for t in rows),
        "chop": sum(t.get("book") == "CHOP" for t in rows),
        "brk": sum(t.get("book") == "BRK" for t in rows),
    }


if __name__ == "__main__":
    main()
