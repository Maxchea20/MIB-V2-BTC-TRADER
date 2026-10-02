"""Chop fade of a failed-push box. Does not touch the Hunt."""

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

FIELDS = ("side", "entry", "stop", "target", "exit", "entry_time", "exit_time", "exit_reason", "r_multiple", "net_pnl")


def main():
    db = research_db_path(sys.argv[1] if len(sys.argv) > 1 else None)
    clock = sys.argv[2] if len(sys.argv) > 2 else "1h"
    bars, info = load_bars(db, "BTC_USDT", None, None)
    series = resample(bars, clock)
    print(f"{db.name} {clock}={len(series)} {info.start_ms}..{info.end_ms}")
    trades, counts = _run(series)
    folder = ROOT / "results" / f"exp-chop-push-{clock}" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "trades.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(trades)
    row = _score(db.name, clock, trades)
    row["counts"] = counts
    row["file"] = str(folder / "trades.csv")
    print(json.dumps(row, indent=2))


def _run(series):
    trades = []
    counts = {"boxes": 0, "fails": 0, "tiny_stop": 0}
    quiet_until = 0
    lookback = 240 if len(series) > 3000 else 180
    for i in range(lookback, len(series) - 1):
        bar = series[i]
        if bar.open_time < quiet_until:
            continue
        state = detect_push_range(series[i - lookback + 1 : i + 1])
        if not state.active or state.phase != "RANGE" or state.high is None:
            continue
        counts["boxes"] += 1
        side = _fail(bar, state.high, state.low)
        if not side:
            continue
        counts["fails"] += 1
        nxt = series[i + 1]
        slip = 0.1 + nxt.open * 0.00005
        entry = nxt.open + slip if side == "LONG" else nxt.open - slip
        stop = bar.low - slip if side == "LONG" else bar.high + slip
        target = (state.high + state.low) / 2
        risk = abs(entry - stop)
        atr = _atr(series[i - 14 : i + 1])
        if risk <= 0 or (atr and risk < 0.25 * atr):
            counts["tiny_stop"] += 1
            continue
        if side == "LONG" and (stop >= entry or target <= entry):
            continue
        if side == "SHORT" and (stop <= entry or target >= entry):
            continue
        trade = {"side": side, "entry": entry, "stop": stop, "target": target, "risk": risk, "entry_time": nxt.open_time}
        done = _walk(trade, series, i + 1)
        if not done:
            continue
        trades.append(done)
        quiet_until = done["exit_time"]
    return trades, counts


def _fail(bar, high, low):
    close = bar.close
    if bar.low < low and low < close <= high and close > bar.open:
        return "LONG"
    if bar.high > high and low <= close < high and close < bar.open:
        return "SHORT"
    return None


def _walk(trade, series, start):
    for bar in series[start:]:
        stop_hit = bar.low <= trade["stop"] if trade["side"] == "LONG" else bar.high >= trade["stop"]
        target_hit = bar.high >= trade["target"] if trade["side"] == "LONG" else bar.low <= trade["target"]
        if not stop_hit and not target_hit:
            continue
        price = trade["stop"] if stop_hit else trade["target"]
        gross = price - trade["entry"] if trade["side"] == "LONG" else trade["entry"] - price
        trade["exit"] = price
        trade["exit_time"] = bar.open_time
        trade["exit_reason"] = "STOP" if stop_hit else "TARGET"
        trade["net_pnl"] = gross - (trade["entry"] + price) * 0.0002
        trade["r_multiple"] = trade["net_pnl"] / trade["risk"]
        return trade
    return None


def _atr(bars):
    if len(bars) < 15:
        return None
    acc = 0.0
    prev = bars[-15].close
    for bar in bars[-14:]:
        acc += max(bar.high - bar.low, abs(bar.high - prev), abs(bar.low - prev))
        prev = bar.close
    return acc / 14 or None


def _score(name, clock, trades):
    if not trades:
        return {"db": name, "clock": clock, "n": 0}
    wins = [t for t in trades if t["net_pnl"] > 0]
    losses = [t for t in trades if t["net_pnl"] <= 0]
    gross_loss = abs(sum(t["net_pnl"] for t in losses))
    equity = peak = dip = 0.0
    for trade in trades:
        equity += trade["r_multiple"]
        peak = max(peak, equity)
        dip = min(dip, equity - peak)
    return {
        "db": name,
        "clock": clock,
        "n": len(trades),
        "expectancy_r": round(sum(t["r_multiple"] for t in trades) / len(trades), 4),
        "profit_factor": round(sum(t["net_pnl"] for t in wins) / gross_loss, 4) if gross_loss else None,
        "drawdown_r": round(dip, 2),
        "stops": sum(t["exit_reason"] == "STOP" for t in trades),
        "targets": sum(t["exit_reason"] == "TARGET" for t in trades),
    }


if __name__ == "__main__":
    main()
