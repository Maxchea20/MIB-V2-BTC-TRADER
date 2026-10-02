"""Desktop Hunt weather compare. Hard V1 against the 1 ATR soften."""

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
    mode = sys.argv[1] if len(sys.argv) > 1 else "weather-v1"
    paths = sys.argv[2:] or [None]
    if mode not in ("weather-v1", "weather-v1b"):
        raise SystemExit("use weather-v1 or weather-v1b")
    rows = []
    for raw in paths:
        db = research_db_path(raw)
        bars, info = load_bars(db, "BTC_USDT", None, None)
        bars_5 = resample(bars, "5m")
        bars_15 = resample(bars, "15m")
        bars_1h = resample(bars, "1h")
        bars_4h = resample(bars, "4h")
        print(f"{db.name} 1m={info.rows} {info.start_ms}..{info.end_ms}")
        trades = _run(bars, bars_5, bars_15, bars_1h, bars_4h, mode == "weather-v1b")
        row = _score(db.name, mode, trades)
        rows.append(row)
        print(json.dumps(row))
    print(json.dumps({"note": "Hard weather is V1. V1b unlocks the other side after a 1 ATR retrace.", "rows": rows}, indent=2))


def _run(bars, bars_5, bars_15, bars_1h, bars_4h, soften):
    trades = []
    open_trade = None
    quiet_until = 0
    atrs = _atr(bars_15)
    for i, bar in enumerate(bars):
        if open_trade and bar["ts"] >= open_trade["entry_time"]:
            done = _fill(open_trade, bar)
            if done:
                trades.append(done)
                quiet_until = done["exit_time"] + 15 * 60_000
                open_trade = None
        if open_trade or bar["ts"] < quiet_until or i + 1 >= len(bars):
            continue
        if (bar["ts"] // FIVE) * FIVE + FIVE != bars[i + 1]["ts"]:
            continue
        slot_end = (bar["ts"] // FIFTEEN) * FIFTEEN + FIFTEEN
        if bar["ts"] + 60_000 != slot_end:
            continue
        j5 = _before(bars_5, slot_end)
        j15 = _before(bars_15, slot_end)
        j1 = _before(bars_1h, slot_end)
        j4 = _before(bars_4h, slot_end)
        if j5 < 1 or j15 < 60 or j4 < 20:
            continue
        side, event = _fresh(bars_15, j15)
        if not side:
            continue
        flag = _weather(bars_4h, j4, bars_1h, j1, soften)
        if flag == "SWING_UP" and side != "LONG":
            continue
        if flag == "SWING_DOWN" and side != "SHORT":
            continue
        level = max(b["high"] for b in bars_15[j15 - 20:j15]) if side == "LONG" else min(b["low"] for b in bars_15[j15 - 20:j15])
        answer = bars_5[j5]
        if side == "LONG" and answer["close"] <= level:
            continue
        if side == "SHORT" and answer["close"] >= level:
            continue
        atr = atrs[j15]
        if not atr:
            continue
        entry = bars[i + 1]["open"]
        slip = 0.1 + entry * 0.00005
        entry = entry + slip if side == "LONG" else entry - slip
        stop = entry - 1.5 * atr if side == "LONG" else entry + 1.5 * atr
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        target = entry + 2.5 * atr if side == "LONG" else entry - 2.5 * atr
        open_trade = {
            "side": side, "event": event, "weather": flag, "entry": entry, "stop": stop,
            "target": target, "risk": risk, "entry_time": bars[i + 1]["ts"],
        }
    return [t for t in trades if t["exit_reason"] != "END_OF_DATA"]


def _fresh(bars, j):
    last = None
    streak = 0
    streak_side = None
    start = max(5, j - 80)
    for i in range(start, j):
        if i + 5 >= j:
            break
        high = bars[i]["high"]
        low = bars[i]["low"]
        if high > max(b["high"] for b in bars[i - 5:i]) and high >= max(b["high"] for b in bars[i + 1:i + 6]):
            side, event = "LONG", "BOS"
        elif low < min(b["low"] for b in bars[i - 5:i]) and low <= min(b["low"] for b in bars[i + 1:i + 6]):
            side, event = "SHORT", "BOS"
        else:
            continue
        if streak_side == side:
            streak += 1
        else:
            streak_side = side
            streak = 1
        last = None if streak >= 3 else (side, event, i)
    if not last or last[2] != j - 6:
        return None, None
    return last[0], last[1]


def _weather(bars_4h, j4, bars_1h, j1, soften):
    rows = bars_4h[:j4]
    atr = _atr(rows)[-1] if len(rows) > 15 else None
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
    if flag != "CHOP" and j1 >= 8:
        u1, d1 = _votes(bars_1h[:j1])
        if flag == "SWING_UP" and d1 >= 5:
            flag = "CHOP"
        elif flag == "SWING_DOWN" and u1 >= 5:
            flag = "CHOP"
    if soften and flag != "CHOP" and atr:
        window = rows[-8:]
        close = rows[-1]["close"]
        retrace = (max(b["high"] for b in window) - close) / atr if flag == "SWING_UP" else (close - min(b["low"] for b in window)) / atr
        if retrace >= 1:
            flag = "CHOP"
    return flag


def _votes(rows):
    up = down = 0
    for a, b in zip(rows[-7:-1], rows[-6:]):
        if b["close"] > a["close"]:
            up += 1
        elif b["close"] < a["close"]:
            down += 1
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


def _before(bars, ts):
    lo, hi = 0, len(bars)
    while lo < hi:
        mid = (lo + hi) // 2
        if bars[mid]["ts"] + _span(bars) <= ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _span(bars):
    return bars[1]["ts"] - bars[0]["ts"] if len(bars) > 1 else 60_000


def _fill(trade, bar):
    side = trade["side"]
    stop_hit = bar["low"] <= trade["stop"] if side == "LONG" else bar["high"] >= trade["stop"]
    target_hit = bar["high"] >= trade["target"] if side == "LONG" else bar["low"] <= trade["target"]
    if not stop_hit and not target_hit:
        return None
    price = trade["stop"] if stop_hit else trade["target"]
    gross = (price - trade["entry"]) if side == "LONG" else (trade["entry"] - price)
    fee = (trade["entry"] + price) * 0.0002
    trade["exit"] = price
    trade["exit_time"] = bar["ts"]
    trade["exit_reason"] = "STOP" if stop_hit else "TARGET"
    trade["net_pnl"] = gross - fee
    trade["r_multiple"] = trade["net_pnl"] / trade["risk"]
    return trade


def _score(name, mode, trades):
    if not trades:
        return {"db": name, "mode": mode, "n": 0}
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
        "mode": mode,
        "n": len(trades),
        "expectancy_r": round(sum(t["r_multiple"] for t in trades) / len(trades), 4),
        "profit_factor": round(sum(t["net_pnl"] for t in wins) / gross_loss, 4) if gross_loss else None,
        "drawdown_r": round(dip, 2),
        "long_n": sum(t["side"] == "LONG" for t in trades),
        "short_n": sum(t["side"] == "SHORT" for t in trades),
    }


if __name__ == "__main__":
    main()
