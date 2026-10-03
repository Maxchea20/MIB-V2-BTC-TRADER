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
    hunt_files = sorted((ROOT / "results" / "exp-hunt-desktop-cfi-v1").glob("*/trades.csv"))
    if not hunt_files:
        raise SystemExit("no full Hunt trades")
    hunt = list(csv.DictReader(hunt_files[-1].open(encoding="utf-8")))
    bars, info = load_bars(db, "BTC_USDT", None, None)
    series = resample(bars, "1h")
    print(f"{db.name} 1h={len(series)} {info.start_ms}..{info.end_ms}")
    active = _flags(series)
    chop = _chop(series, active)
    kept = [t for t in hunt if not _on(int(t["entry_time"]), active)]
    for trade in kept:
        trade["book"] = "HUNT"
    merged = _one_position(kept, chop)
    folder = ROOT / "results" / "exp-hunt-chop-arbiter" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "trades.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(merged)
    print(json.dumps({
        "hunt": _bucket(hunt),
        "hunt_outside_box": _bucket(kept),
        "chop": _bucket(chop),
        "one_position": _bucket(merged),
        "file": str(folder / "trades.csv"),
    }, indent=2))


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
        trade["net_pnl"] = gross - (trade["entry"] + price) * 0.0002
        trade["r_multiple"] = trade["net_pnl"] / trade["risk"]
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
    }


if __name__ == "__main__":
    main()
