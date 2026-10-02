"""Chop fade: 1h box, 5m break confirmation, next 1m open. Hunt is not used."""

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
    bars, info = load_bars(db, "BTC_USDT", None, None)
    bars_5 = resample(bars, "5m")
    bars_1h = resample(bars, "1h")
    opens = {b.open_time: b for b in bars}
    print(f"{db.name} 1m={len(bars)} 5m={len(bars_5)} {info.start_ms}..{info.end_ms}")
    trades, counts = _run(bars, bars_5, bars_1h, opens)
    folder = ROOT / "results" / "exp-chop-5m-1m" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "trades.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(trades)
    row = _score(db.name, trades)
    row["counts"] = counts
    row["file"] = str(folder / "trades.csv")
    print(json.dumps(row, indent=2))


def _run(bars, bars_5, bars_1h, opens):
    trades = []
    counts = {"boxes": 0, "breaks": 0}
    quiet_until = 0
    hour_i = 0
    for i in range(20, len(bars_5) - 1):
        bar = bars_5[i]
        if bar.open_time < quiet_until:
            continue
        while hour_i < len(bars_1h) and bars_1h[hour_i].open_time + 3_600_000 <= bar.open_time:
            hour_i += 1
        hour = bars_1h[max(0, hour_i - 240):hour_i]
        state = detect_push_range(hour)
        if not state.active or state.phase != "RANGE" or state.high is None:
            continue
        counts["boxes"] += 1
        side, stop = _break(bars_5[i - 20 : i + 1], state.high, state.low)
        if not side:
            continue
        counts["breaks"] += 1
        entry_time = bar.open_time + 300_000
        nxt = opens.get(entry_time)
        if nxt is None:
            continue
        slip = 0.1 + nxt.open * 0.00005
        entry = nxt.open + slip if side == "LONG" else nxt.open - slip
        stop = stop - slip if side == "LONG" else stop + slip
        target = (state.high + state.low) / 2
        risk = abs(entry - stop)
        if side == "LONG" and (stop >= entry or target <= entry):
            continue
        if side == "SHORT" and (stop <= entry or target >= entry):
            continue
        trade = {"side": side, "entry": entry, "stop": stop, "target": target, "risk": risk, "entry_time": nxt.open_time}
        done = _walk(trade, bars, entry_time)
        if not done:
            continue
        trades.append(done)
        quiet_until = done["exit_time"]
    return trades, counts


def _break(window, high, low):
    bar = window[-1]
    if bar.close < low or bar.close > high:
        return None, None
    swing_high = max(b.high for b in window[:-3])
    swing_low = min(b.low for b in window[:-3])
    mid = (high + low) / 2
    if bar.close > swing_high and bar.close <= mid and bar.close > bar.open:
        return "LONG", min(b.low for b in window[-5:])
    if bar.close < swing_low and bar.close >= mid and bar.close < bar.open:
        return "SHORT", max(b.high for b in window[-5:])
    return None, None


def _walk(trade, bars, entry_time):
    for bar in bars:
        if bar.open_time < entry_time:
            continue
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


def _score(name, trades):
    if not trades:
        return {"db": name, "n": 0}
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
        "n": len(trades),
        "expectancy_r": round(sum(t["r_multiple"] for t in trades) / len(trades), 4),
        "profit_factor": round(sum(t["net_pnl"] for t in wins) / gross_loss, 4) if gross_loss else None,
        "drawdown_r": round(dip, 2),
        "stops": sum(t["exit_reason"] == "STOP" for t in trades),
        "targets": sum(t["exit_reason"] == "TARGET" for t in trades),
    }


if __name__ == "__main__":
    main()
