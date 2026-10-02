"""One backtest of the desktop Hunt C-FI history. Weather V1, no soften."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample

FIVE = 300_000
FIFTEEN = 900_000


def main():
    paths = sys.argv[1:] or [None]
    rows = []
    for raw in paths:
        db = research_db_path(raw)
        bars, info = load_bars(db, "BTC_USDT", None, None)
        print(f"{db.name} 1m={info.rows} {info.start_ms}..{info.end_ms}")
        row = _score(db.name, _run(bars, resample(bars, "5m"), resample(bars, "15m"), resample(bars, "1h"), resample(bars, "4h")))
        rows.append(row)
        print(json.dumps(row))
    print(json.dumps({"note": "Desktop C-FI history. Weather V1. Same-bar stop wins.", "rows": rows}, indent=2))


def _run(bars, bars_5, bars_15, bars_1h, bars_4h):
    trades = []
    open_trade = None
    quiet_until = 0
    atrs = _atr(bars_15)
    for j, bar in enumerate(bars_5):
        slot_start = (bar["ts"] // FIFTEEN) * FIFTEEN
        if bar["ts"] != slot_start and bar["ts"] != slot_start + FIVE and bar["ts"] != slot_start + 2 * FIVE:
            continue
        slot = (bar["ts"] - slot_start) // FIVE + 1
        live = [b for b in bars_5[max(0, j - 2):j + 1] if b["ts"] >= slot_start]
        j15 = _closed(bars_15, slot_start, FIFTEEN)
        j4 = _closed(bars_4h, bar["ts"] + FIVE, 14_400_000)
        j1 = _closed(bars_1h, bar["ts"] + FIVE, 3_600_000)
        if j15 < 60 or j4 < 20 or not atrs[j15 - 1]:
            continue
        side, event, gate = _gate(bars_15, j15)
        if not side:
            continue
        flag = _weather(bars_4h[:j4], bars_1h[:j1])
        if flag == "SWING_UP" and side != "LONG":
            continue
        if flag == "SWING_DOWN" and side != "SHORT":
            continue
        level = bars_15[j15 - 1]["high"] if side == "LONG" else bars_15[j15 - 1]["low"]
        if not _answers(side, level, live, slot, atrs[j15 - 1]):
            continue
        entry_time = bar["ts"] + FIVE
        if open_trade and entry_time >= open_trade["entry_time"]:
            done = _walk(open_trade, bars, open_trade["entry_time"], entry_time)
            if done:
                trades.append(done)
                quiet_until = done["exit_time"] + 15 * 60_000
                open_trade = None
            else:
                continue
        if entry_time < quiet_until:
            continue
        atr = atrs[j15 - 1]
        slip = 0.1 + level * 0.00005
        entry = level + slip if side == "LONG" else level - slip
        stop = entry - 1.5 * atr if side == "LONG" else entry + 1.5 * atr
        target = entry + 2.5 * atr if side == "LONG" else entry - 2.5 * atr
        open_trade = {
            "side": side, "event": event, "gate": gate, "weather": flag,
            "entry": entry, "stop": stop, "target": target, "risk": abs(entry - stop),
            "entry_time": entry_time, "fill_bar": bar,
        }
        done = _walk(open_trade, bars, entry_time, entry_time + FIVE)
        if done:
            trades.append(done)
            quiet_until = done["exit_time"] + 15 * 60_000
            open_trade = None
    if open_trade:
        done = _walk(open_trade, bars, open_trade["entry_time"], bars[-1]["ts"] + 60_000)
        if done:
            trades.append(done)
    return [t for t in trades if t["exit_reason"] != "END_OF_DATA"]


def _gate(bars, j):
    fast = _event(bars, j, 5)
    if fast and fast[2] == j - 6:
        return fast[0], fast[1], "cfast"
    internal = _event(bars, j, 2)
    if internal and internal[2] == j - 3:
        return internal[0], internal[1], "internal"
    lingering = fast or internal
    if not lingering:
        return None, None, None
    return lingering[0], lingering[1], "rearm"


def _event(bars, j, lr):
    last = None
    streak = 0
    streak_side = None
    for i in range(lr, j - lr):
        high, low = bars[i]["high"], bars[i]["low"]
        left, right = bars[i - lr:i], bars[i + 1:i + 1 + lr]
        if high > max(b["high"] for b in left) and high >= max(b["high"] for b in right):
            side = "LONG"
        elif low < min(b["low"] for b in left) and low <= min(b["low"] for b in right):
            side = "SHORT"
        else:
            continue
        event = "CHoCH" if streak_side not in (None, side) else "BOS"
        streak = streak + 1 if streak_side == side else 1
        streak_side = side
        last = None if event == "BOS" and streak >= 3 else (side, event, i + lr)
    return last


def _answers(side, level, live, slot, atr):
    close = live[-1]["close"]
    if side == "LONG" and close > level and close - level >= 0.15 * atr:
        return True
    if side == "SHORT" and close < level and level - close >= 0.15 * atr:
        return True
    if slot < 2:
        return False
    if side == "LONG" and max(b["high"] for b in live[:-1]) > level and close >= level:
        return True
    if side == "SHORT" and min(b["low"] for b in live[:-1]) < level and close <= level:
        return True
    return False


def _weather(rows, rows_1h):
    atr = _atr(rows)[-1]
    old = _atr(rows[:-10])[-1] if len(rows) >= 24 else None
    opening = bool(atr and old and old > 0 and atr / old >= 1.4)
    up, down = _votes(rows)
    close_side = "SWING_UP" if up >= 5 else ("SWING_DOWN" if down >= 5 else None)
    body = _body(rows[-1])
    su = int(opening and close_side != "SWING_DOWN") + int(close_side == "SWING_UP") + int(body == "SWING_UP")
    sd = int(opening and close_side != "SWING_UP") + int(close_side == "SWING_DOWN") + int(body == "SWING_DOWN")
    if close_side == "SWING_UP":
        su = max(su, 2)
    if close_side == "SWING_DOWN":
        sd = max(sd, 2)
    flag = "SWING_UP" if su >= 2 and su > sd else ("SWING_DOWN" if sd >= 2 and sd > su else "CHOP")
    if flag != "CHOP" and len(rows_1h) >= 8:
        u1, d1 = _votes(rows_1h)
        if (flag == "SWING_UP" and d1 >= 5) or (flag == "SWING_DOWN" and u1 >= 5):
            flag = "CHOP"
    return flag


def _votes(rows):
    up = down = 0
    for a, b in zip(rows[-7:-1], rows[-6:]):
        up += b["close"] > a["close"]
        down += b["close"] < a["close"]
    return up, down


def _body(bar):
    span = bar["high"] - bar["low"]
    if span <= 0 or abs(bar["close"] - bar["open"]) / span < 0.5:
        return None
    third = span / 3
    if bar["close"] >= bar["high"] - third and bar["close"] > bar["open"]:
        return "SWING_UP"
    if bar["close"] <= bar["low"] + third and bar["close"] < bar["open"]:
        return "SWING_DOWN"
    return None


def _atr(bars):
    out = [None] * len(bars)
    for i in range(15, len(bars)):
        acc = 0.0
        prev = bars[i - 14]["close"]
        for bar in bars[i - 13:i + 1]:
            acc += max(bar["high"] - bar["low"], abs(bar["high"] - prev), abs(bar["low"] - prev))
            prev = bar["close"]
        out[i] = acc / 14
    return out


def _closed(bars, ts, span):
    lo, hi = 0, len(bars)
    while lo < hi:
        mid = (lo + hi) // 2
        if bars[mid]["ts"] + span <= ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _walk(trade, bars, start, end):
    side = trade["side"]
    for bar in bars:
        if bar["ts"] < start or bar["ts"] >= end:
            continue
        stop_hit = bar["low"] <= trade["stop"] if side == "LONG" else bar["high"] >= trade["stop"]
        target_hit = bar["high"] >= trade["target"] if side == "LONG" else bar["low"] <= trade["target"]
        if not stop_hit and not target_hit:
            continue
        price = trade["stop"] if stop_hit else trade["target"]
        gross = price - trade["entry"] if side == "LONG" else trade["entry"] - price
        trade["exit"] = price
        trade["exit_time"] = bar["ts"]
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
        "cfast": sum(t["gate"] == "cfast" for t in trades),
        "internal": sum(t["gate"] == "internal" for t in trades),
        "rearm": sum(t["gate"] == "rearm" for t in trades),
        "long_n": sum(t["side"] == "LONG" for t in trades),
        "short_n": sum(t["side"] == "SHORT" for t in trades),
    }


if __name__ == "__main__":
    main()
