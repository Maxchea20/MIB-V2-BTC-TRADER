"""Chop failed-break, long only. Does not touch the full Hunt."""

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

FIVE = 300_000
FIFTEEN = 900_000
FIELDS = ("side", "entry", "stop", "target", "exit", "entry_time", "exit_time", "exit_reason", "r_multiple", "net_pnl")


def main():
    db = research_db_path(sys.argv[1] if len(sys.argv) > 1 else None)
    bars, info = load_bars(db, "BTC_USDT", None, None)
    print(f"{db.name} 1m={info.rows} {info.start_ms}..{info.end_ms}")
    trades, counts = _run(bars, resample(bars, "5m"), resample(bars, "15m"))
    folder = ROOT / "results" / "exp-chop-fail-long-v1" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "trades.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(trades)
    row = _score(db.name, trades)
    row["counts"] = counts
    row["file"] = str(folder / "trades.csv")
    print(json.dumps(row, indent=2))


def _run(bars, bars_5, bars_15):
    trades = []
    counts = {"ranges": 0, "sweeps": 0, "reclaims": 0, "triggers": 0}
    atrs = _atr(bars_15)
    quiet_until = 0
    sweep = None
    for bar in bars_5:
        j15 = _closed(bars_15, bar.open_time + FIVE, FIFTEEN)
        if j15 < 21 or not atrs[j15 - 1]:
            continue
        window = bars_15[j15 - 20:j15]
        range_low = min(b.low for b in window)
        range_high = max(b.high for b in window)
        atr = atrs[j15 - 1]
        if range_high - range_low < atr:
            continue
        counts["ranges"] += 1
        if sweep and bar.open_time > sweep["deadline"]:
            sweep = None
        if sweep is None and bar.low < range_low and bar.open_time >= quiet_until:
            edge = range_low + 0.25 * (range_high - range_low)
            if bar.open <= edge:
                sweep = {
                    "low": bar.low,
                    "deadline": bar.open_time + 30 * 60_000,
                    "range_low": range_low,
                    "range_high": range_high,
                }
                counts["sweeps"] += 1
            continue
        if not sweep:
            continue
        sweep["low"] = min(sweep["low"], bar.low)
        if bar.close <= sweep["range_low"]:
            continue
        counts["reclaims"] += 1
        held = sweep
        sweep = None
        trigger = _trigger(bars, bar.open_time + FIVE, held["range_low"])
        if not trigger:
            continue
        counts["triggers"] += 1
        entry_time, entry_open = trigger
        if entry_time < quiet_until:
            continue
        slip = 0.1 + entry_open * 0.00005
        entry = entry_open + slip
        stop = held["low"] - slip
        target = (held["range_low"] + held["range_high"]) / 2
        if target <= entry or stop >= entry:
            continue
        trade = {
            "side": "LONG", "entry": entry, "stop": stop, "target": target,
            "risk": entry - stop, "entry_time": entry_time,
        }
        done = _walk(trade, bars, entry_time, bars[-1].open_time + 60_000)
        if not done or done["exit_reason"] == "END_OF_DATA":
            continue
        trades.append(done)
        quiet_until = done["exit_time"] + FIFTEEN
    return trades, counts


def _trigger(bars, reclaim_time, level):
    lo, hi = 0, len(bars)
    while lo < hi:
        mid = (lo + hi) // 2
        if bars[mid].open_time < reclaim_time:
            lo = mid + 1
        else:
            hi = mid
    for i, bar in enumerate(bars[lo:lo + 30], start=lo):
        if bar.close > bar.open and bar.close > level and i + 1 < len(bars):
            return bars[i + 1].open_time, bars[i + 1].open
    return None


def _atr(bars):
    out = [None] * len(bars)
    for i in range(15, len(bars)):
        acc = 0.0
        prev = bars[i - 14].close
        for bar in bars[i - 13:i + 1]:
            acc += max(bar.high - bar.low, abs(bar.high - prev), abs(bar.low - prev))
            prev = bar.close
        out[i] = acc / 14
    return out


def _closed(bars, ts, span):
    lo, hi = 0, len(bars)
    while lo < hi:
        mid = (lo + hi) // 2
        if bars[mid].open_time + span <= ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _walk(trade, bars, start, end):
    lo, hi = 0, len(bars)
    while lo < hi:
        mid = (lo + hi) // 2
        if bars[mid].open_time < start:
            lo = mid + 1
        else:
            hi = mid
    for bar in bars[lo:]:
        if bar.open_time >= end:
            break
        stop_hit = bar.low <= trade["stop"]
        target_hit = bar.high >= trade["target"]
        if not stop_hit and not target_hit:
            continue
        price = trade["stop"] if stop_hit else trade["target"]
        gross = price - trade["entry"]
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
