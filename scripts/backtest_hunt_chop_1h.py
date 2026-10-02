"""Hunt chop test. 1h must agree in chop. 15m structure, 5m confirm, next 1m open."""

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
FIELDS = ("side", "event", "gate", "weather", "entry", "stop", "target", "exit", "entry_time", "exit_time", "exit_reason", "r_multiple", "net_pnl")


def main():
    db = research_db_path(sys.argv[1] if len(sys.argv) > 1 else None)
    bars, info = load_bars(db, "BTC_USDT", None, None)
    print(f"{db.name} 1m={info.rows} {info.start_ms}..{info.end_ms}")
    trades = _run(bars, resample(bars, "5m"), resample(bars, "15m"), resample(bars, "1h"), resample(bars, "4h"))
    folder = ROOT / "results" / "exp-hunt-chop-1h-v1" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "trades.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(trades)
    row = _score(db.name, trades)
    row["file"] = str(folder / "trades.csv")
    print(json.dumps(row, indent=2))


def _run(bars, bars_5, bars_15, bars_1h, bars_4h):
    trades = []
    open_trade = None
    quiet_until = 0
    atrs = _atr(bars_15)
    atrs_4h = _atr(bars_4h)
    fast = _events(bars_15, 5)
    internal = _events(bars_15, 2)
    opens = {bar.open_time: bar.open for bar in bars}
    for j, bar in enumerate(bars_5):
        slot_start = (bar.open_time // FIFTEEN) * FIFTEEN
        if bar.open_time not in (slot_start, slot_start + FIVE, slot_start + 2 * FIVE):
            continue
        slot = (bar.open_time - slot_start) // FIVE + 1
        live = [b for b in bars_5[max(0, j - 2):j + 1] if b.open_time >= slot_start]
        j15 = _closed(bars_15, slot_start, FIFTEEN)
        j4 = _closed(bars_4h, bar.open_time + FIVE, 14_400_000)
        j1 = _closed(bars_1h, bar.open_time + FIVE, 3_600_000)
        if j15 < 60 or j4 < 20 or j1 < 8 or not atrs[j15 - 1]:
            continue
        side, event, gate = _gate(fast, internal, j15)
        if not side:
            continue
        flag = _weather(bars_4h[:j4], bars_1h[:j1], atrs_4h)
        if flag == "SWING_UP" and side != "LONG":
            continue
        if flag == "SWING_DOWN" and side != "SHORT":
            continue
        if flag == "CHOP" and not _hour_agrees(bars_1h[:j1], side):
            continue
        level = bars_15[j15 - 1].high if side == "LONG" else bars_15[j15 - 1].low
        if not _answers(side, level, live, slot, atrs[j15 - 1]):
            continue
        entry_time = bar.open_time + FIVE
        if entry_time not in opens:
            continue
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
        slip = 0.1 + opens[entry_time] * 0.00005
        entry = opens[entry_time] + slip if side == "LONG" else opens[entry_time] - slip
        open_trade = {
            "side": side, "event": event, "gate": gate, "weather": flag,
            "entry": entry,
            "stop": entry - 1.5 * atr if side == "LONG" else entry + 1.5 * atr,
            "target": entry + 2.5 * atr if side == "LONG" else entry - 2.5 * atr,
            "risk": 1.5 * atr, "entry_time": entry_time,
        }
        done = _walk(open_trade, bars, entry_time, entry_time + 60_000)
        if done:
            trades.append(done)
            quiet_until = done["exit_time"] + 15 * 60_000
            open_trade = None
    if open_trade:
        done = _walk(open_trade, bars, open_trade["entry_time"], bars[-1].open_time + 60_000)
        if done:
            trades.append(done)
    return [t for t in trades if t["exit_reason"] != "END_OF_DATA"]


def _hour_agrees(rows, side):
    up = down = 0
    for a, b in zip(rows[-7:-1], rows[-6:]):
        up += b.close > a.close
        down += b.close < a.close
    if side == "LONG":
        return up >= 4 and up > down
    return down >= 4 and down > up


def _events(bars, lr):
    out = [None] * len(bars)
    last = None
    streak = 0
    streak_side = None
    for i in range(lr, len(bars) - lr):
        left, right = bars[i - lr:i], bars[i + 1:i + 1 + lr]
        if bars[i].high > max(b.high for b in left) and bars[i].high >= max(b.high for b in right):
            side = "LONG"
        elif bars[i].low < min(b.low for b in left) and bars[i].low <= min(b.low for b in right):
            side = "SHORT"
        else:
            out[i + lr] = last
            continue
        event = "CHoCH" if streak_side not in (None, side) else "BOS"
        streak = streak + 1 if streak_side == side else 1
        streak_side = side
        last = None if event == "BOS" and streak >= 3 else (side, event, i + lr)
        out[i + lr] = last
    for i in range(1, len(out)):
        if out[i] is None:
            out[i] = out[i - 1]
    return out


def _gate(fast, internal, j):
    got = fast[j - 1] if j else None
    if got and got[2] == j - 1:
        return got[0], got[1], "cfast"
    got = internal[j - 1] if j else None
    if got and got[2] == j - 1:
        return got[0], got[1], "internal"
    lingering = (fast[j - 1] if j else None) or (internal[j - 1] if j else None)
    if not lingering:
        return None, None, None
    return lingering[0], lingering[1], "rearm"


def _answers(side, level, live, slot, atr):
    close = live[-1].close
    if side == "LONG" and close > level and close - level >= 0.15 * atr:
        return True
    if side == "SHORT" and close < level and level - close >= 0.15 * atr:
        return True
    if slot < 2:
        return False
    if side == "LONG" and max(b.high for b in live[:-1]) > level and close >= level:
        return True
    if side == "SHORT" and min(b.low for b in live[:-1]) < level and close <= level:
        return True
    return False


def _weather(rows, rows_1h, atrs):
    atr = atrs[len(rows) - 1]
    old = atrs[len(rows) - 11] if len(rows) >= 24 else None
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
        up += b.close > a.close
        down += b.close < a.close
    return up, down


def _body(bar):
    span = bar.high - bar.low
    if span <= 0 or abs(bar.close - bar.open) / span < 0.5:
        return None
    third = span / 3
    if bar.close >= bar.high - third and bar.close > bar.open:
        return "SWING_UP"
    if bar.close <= bar.low + third and bar.close < bar.open:
        return "SWING_DOWN"
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
    side = trade["side"]
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
        stop_hit = bar.low <= trade["stop"] if side == "LONG" else bar.high >= trade["stop"]
        target_hit = bar.high >= trade["target"] if side == "LONG" else bar.low <= trade["target"]
        if not stop_hit and not target_hit:
            continue
        price = trade["stop"] if stop_hit else trade["target"]
        gross = price - trade["entry"] if side == "LONG" else trade["entry"] - price
        trade["exit"] = price
        trade["exit_time"] = bar.open_time
        trade["exit_reason"] = "STOP" if stop_hit else "TARGET"
        trade["net_pnl"] = gross - (trade["entry"] + price) * 0.0002
        trade["r_multiple"] = trade["net_pnl"] / trade["risk"]
        return trade
    return None


def _bucket(trades):
    if not trades:
        return {"n": 0}
    wins = [t for t in trades if t["net_pnl"] > 0]
    losses = [t for t in trades if t["net_pnl"] <= 0]
    gross_loss = abs(sum(t["net_pnl"] for t in losses))
    equity = peak = dip = 0.0
    for trade in trades:
        equity += trade["r_multiple"]
        peak = max(peak, equity)
        dip = min(dip, equity - peak)
    return {
        "n": len(trades),
        "expectancy_r": round(sum(t["r_multiple"] for t in trades) / len(trades), 4),
        "profit_factor": round(sum(t["net_pnl"] for t in wins) / gross_loss, 4) if gross_loss else None,
        "drawdown_r": round(dip, 2),
        "stops": sum(t["exit_reason"] == "STOP" for t in trades),
        "targets": sum(t["exit_reason"] == "TARGET" for t in trades),
    }


def _score(name, trades):
    out = {"db": name, "combined": _bucket(trades)}
    out["by_side"] = {side: _bucket([t for t in trades if t["side"] == side]) for side in ("LONG", "SHORT")}
    out["by_weather"] = {flag: _bucket([t for t in trades if t["weather"] == flag]) for flag in ("SWING_UP", "SWING_DOWN", "CHOP")}
    return out


if __name__ == "__main__":
    main()
