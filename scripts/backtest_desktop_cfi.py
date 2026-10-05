"""Desktop Hunt C-FI. trail-1atr follows 1 ATR behind the best price after 1 ATR in favor."""

import bisect
import csv
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.execution import ExecutionConfig, market_fill
from btc_research.execution.options import config_from_args
from btc_research.setups import hunt_exits

FIVE = 300_000
NO_FLOORS = dict(tiers=())   # plain Hunt: stop 1.5 ATR, target 2.5 ATR, nothing else
FIFTEEN = 900_000
FIELDS = ("side", "event", "gate", "weather", "entry", "stop", "target", "exit", "entry_time", "exit_time", "exit_reason", "r_multiple", "net_pnl", "level", "signal_time", "signal_side", "signal_level", "signal_price", "order_submit_time", "order_type", "intended_entry_price", "fill_status", "fill_time", "entry_raw", "entry_slippage", "execution_model", "latency_ms", "fill_reference", "fake_fill_removed", "exit_raw", "exit_slippage", "exit_order_type", "exit_liquidity", "fees", "gross_r_before_costs")


def main():
    args = sys.argv[1:]
    trail = "trail-1atr" in args
    room = "room-ex" if "room-ex" in args else ("room" if "room" in args else None)
    block = "room-block" in args
    exitmode = next((m for m in hunt_exits.MODES if m in args), None)
    fakefill = "fakefill" in args   # "realfill" is still accepted and does nothing: real fill is now the only default
    ideal_exits = "ideal-exits" in args
    exec_cfg, _ = config_from_args(args)
    gate_arg = next((a.split("=", 1)[1] for a in args if a.startswith("trend-gate=")), None)
    trend_gate = (gate_arg, 20) if gate_arg else None
    atr_unit = next((a.split("=", 1)[1] for a in args if a.startswith("atr-unit=")), "15m")
    flags = ("trail-1atr", "room", "room-ex", "room-block", "realfill", "fakefill", "ideal-exits") + tuple(hunt_exits.MODES)
    paths = [a for a in args if a not in flags and "=" not in a] or [None]
    for raw in paths:
        db = research_db_path(raw)
        bars, info = load_bars(db, "BTC_USDT", None, None)
        print(f"{db.name} 1m={info.rows} trail_1atr={trail}")
        events = []
        trades = _run(bars, resample(bars, "5m"), resample(bars, "15m"), resample(bars, "1h"), resample(bars, "4h"), trail, room, block, exitmode, fakefill, exec_cfg, events, ideal_exits, trend_gate, atr_unit)
        name = "exp-hunt-desktop-cfi-trail1" if trail else "exp-hunt-desktop-cfi-v1"
        if room:
            name = f"exp-hunt-desktop-cfi-{room}{'-block' if block else ''}"
        if exitmode:
            name = f"exp-hunt-desktop-cfi-{exitmode}"
        if fakefill:
            name += "-fakefill"
        if trend_gate:
            name += f"-gate{trend_gate[0]}"
        if atr_unit != "15m":
            name += f"-unit{atr_unit}"
        folder = ROOT / "results" / name / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / "trades.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, FIELDS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(trades)
        row = _score(db.name, trades)
        row["trail_1atr"] = trail
        row["room"] = room
        row["room_block"] = block
        row["exitmode"] = exitmode
        row["fakefill"] = fakefill
        row["ideal_exits"] = ideal_exits
        row["trend_gate"] = trend_gate
        row["atr_unit"] = atr_unit
        row["execution"] = None if fakefill else asdict(exec_cfg)
        counts = {}
        for e in events:
            counts[e["status"]] = counts.get(e["status"], 0) + 1
        row["fires"] = {"total": len(events), **counts}
        row["file"] = str(folder / "trades.csv")
        print(json.dumps(row, indent=2))


def _run(bars, bars_5, bars_15, bars_1h, bars_4h, trail, room=None, block=False, exitmode=None, fakefill=False, exec_cfg=None, events=None, ideal_exits=False, trend_gate=None, atr_unit="15m"):
    """Hunt engine. SIGNAL (a FIRE) -> order -> fill or MISSED_FILL -> position -> exit. The strategy part (gate, weather, level, the 5m close answer)
    is unchanged. Who gets filled, at what price and when is decided by btc_research.execution.
    fakefill     the old invalid fill at the level with idealised exits (reproduces the pre-2026-10-04 numbers)
    ideal_exits  real entry fill but the old idealised exits (to see what the exit model costs)
    events       a list that receives one dict per FIRE (filled, skipped or missed), so nothing is silently dropped.
    trend_gate   optional ("1h"|"4h", lookback): only take FIREs in the direction of that trend (last closed close vs the close `lookback` bars earlier).
                 A FIRE against the trend is recorded as FILTERED_TREND_GATE. Default None = Hunt unchanged.
    atr_unit     "15m" (Hunt as designed) or "1h": the ATR that sizes stop 1.5 / target 2.5 / floors. Default unchanged."""
    exec_cfg = None if fakefill else (exec_cfg or ExecutionConfig())
    walk_cfg = None if (fakefill or ideal_exits) else exec_cfg
    if exec_cfg is not None and not exitmode:
        exitmode = NO_FLOORS      # plain Hunt through the same walker, so exits are filled by the simulator
    trades = []
    times_1m = [b.open_time for b in bars]
    open_trade = None
    quiet_until = 0
    atrs = _atr(bars_15)
    atrs_4h = _atr(bars_4h)
    atrs_1h = _atr(bars_1h) if atr_unit == "1h" else None
    gate_bars, gate_span = ((bars_1h, 3_600_000) if trend_gate and trend_gate[0] == "1h" else (bars_4h, 14_400_000)) if trend_gate else (None, None)
    fast = _events(bars_15, 5)
    internal = _events(bars_15, 2)

    def note(fire, status, reason=""):
        if events is not None:
            events.append(dict(fire, status=status, reason=reason))

    def book(done):
        nonlocal quiet_until, open_trade
        quiet_until = done["exit_time"] + 15 * 60_000
        open_trade = None
        if done["exit_reason"] == "UNRESOLVED_BOTH_HIT":
            note(done["_fire"], "UNRESOLVED_BOTH_HIT", "stop and target in the same 1m bar, policy=unresolved")
        else:
            trades.append(done)

    for j, bar in enumerate(bars_5):
        slot_start = (bar.open_time // FIFTEEN) * FIFTEEN
        if bar.open_time not in (slot_start, slot_start + FIVE, slot_start + 2 * FIVE):
            continue
        slot = (bar.open_time - slot_start) // FIVE + 1
        live = [b for b in bars_5[max(0, j - 2):j + 1] if b.open_time >= slot_start]
        j15 = _closed(bars_15, slot_start, FIFTEEN)
        j4 = _closed(bars_4h, bar.open_time + FIVE, 14_400_000)
        j1 = _closed(bars_1h, bar.open_time + FIVE, 3_600_000)
        if j15 < 60 or j4 < 20 or not atrs[j15 - 1]:
            continue
        side, event, gate = _gate(fast, internal, j15)
        if not side:
            continue
        flag = _weather(bars_4h[:j4], bars_1h[:j1], atrs_4h, room)
        if flag == "CHOP_VETO" and block:
            continue
        if flag == "SWING_UP" and side != "LONG":
            continue
        if flag == "SWING_DOWN" and side != "SHORT":
            continue
        level = bars_15[j15 - 1].high if side == "LONG" else bars_15[j15 - 1].low
        if not _answers(side, level, live, slot, atrs[j15 - 1]):
            continue
        # ---- SIGNAL: the 5m candle has closed. This is the earliest moment Hunt can know the condition is true.
        signal_bar = live[-1]
        signal_time = signal_bar.close_time
        fire = {"signal_time": signal_time, "signal_side": side, "signal_level": level, "signal_price": signal_bar.close, "event": event, "gate": gate, "weather": flag, "atr": atrs[j15 - 1]}
        if trend_gate:
            n = _closed(gate_bars, signal_time, gate_span)
            lb = trend_gate[1]
            if n <= lb:
                note(fire, "FILTERED_TREND_GATE", "not enough history")
                continue
            now_c, then_c = gate_bars[n - 1].close, gate_bars[n - 1 - lb].close
            trend = "LONG" if now_c > then_c else ("SHORT" if now_c < then_c else None)
            if trend != side:
                note(fire, "FILTERED_TREND_GATE", f"{trend_gate[0]} trend {trend}")
                continue
        if open_trade and signal_time >= open_trade["entry_time"]:
            done = _walk(open_trade, bars, open_trade["entry_time"], signal_time, walk_cfg)
            if done:
                book(done)
            else:
                note(fire, "SKIPPED_POSITION_OPEN")
                continue
        if signal_time < quiet_until:
            note(fire, "SKIPPED_PAUSE")
            continue
        atr = atrs[j15 - 1]
        if atr_unit == "1h":
            atr = atrs_1h[j1 - 1] if j1 and atrs_1h[j1 - 1] else None
            if not atr:
                note(fire, "SKIPPED_NO_ATR")
                continue
        # ---- ORDER -> EXECUTION
        if fakefill:
            # OLD FAKE FILL, kept only to reproduce the invalid pre-2026-10-04 numbers: the level is a trigger price, not a price you could get.
            slip = 0.1 + level * 0.00005
            execution = {"status": "FILLED", "fill_time": signal_time, "fill_price": level + slip if side == "LONG" else level - slip, "raw": level,
                         "slippage": slip, "submit_time": signal_time, "model": "LEVEL_FAKE"}
        else:
            fill = market_fill(bars, times_1m, side, signal_time + exec_cfg.latency_ms, exec_cfg, entering=True, intended=signal_bar.close)
            if fill.status != "FILLED":
                note(fire, "MISSED_FILL", fill.reason)
                continue
            execution = {"status": "FILLED", "fill_time": fill.fill_time, "fill_price": fill.fill_price, "raw": fill.raw_price, "slippage": fill.slippage,
                         "submit_time": fill.submit_time, "model": fill.execution_model}
        entry = execution["fill_price"]
        open_trade = {
            "side": side, "event": event, "gate": gate, "weather": flag,
            "signal_time": signal_time, "signal_side": side, "signal_level": level, "level": level, "signal_price": signal_bar.close,
            "order_submit_time": execution["submit_time"], "order_type": "MARKET", "intended_entry_price": signal_bar.close,
            "fill_status": "FILLED", "fill_time": execution["fill_time"], "entry_raw": execution["raw"], "entry_slippage": execution["slippage"],
            "execution_model": execution["model"], "latency_ms": execution["fill_time"] - signal_time,
            "fill_reference": execution["model"], "fake_fill_removed": not fakefill,
            "entry": entry,
            "stop": entry - 1.5 * atr if side == "LONG" else entry + 1.5 * atr,
            "target": entry + 2.5 * atr if side == "LONG" else entry - 2.5 * atr,
            "arm": entry + atr if side == "LONG" else entry - atr,
            "atr": atr, "trail": trail, "risk": 1.5 * atr, "entry_time": execution["fill_time"], "exitmode": exitmode, "_fire": fire,
        }
        note(fire, "ORDER_FILLED")
        done = _walk(open_trade, bars, open_trade["entry_time"], signal_time + FIVE, walk_cfg)
        if done:
            book(done)
    if open_trade:
        done = _walk(open_trade, bars, open_trade["entry_time"], bars[-1].open_time + 60_000, walk_cfg)
        if done:
            book(done)
    return [t for t in trades if t["exit_reason"] != "END_OF_DATA"]


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


def _weather(rows, rows_1h, atrs, room=None):
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
    if room and flag != "CHOP" and atr:
        window = rows[-7:] if room == "room" else rows[-7:-1]
        close = rows[-1].close
        gap = max(b.high for b in window) - close if flag == "SWING_UP" else close - min(b.low for b in window)
        if gap < 0.25 * atr:
            flag = "CHOP_VETO"
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


def _walk(trade, bars, start, end, exec_cfg=None):
    if trade.get("exitmode"):
        return hunt_exits.walk(trade, bars, start, end, trade["exitmode"], exec_cfg)
    side = trade["side"]
    lo, hi = 0, len(bars)
    while lo < hi:
        mid = (lo + hi) // 2
        if bars[mid].open_time < start:
            lo = mid + 1
        else:
            hi = mid
    armed = False
    best = trade["entry"]
    for bar in bars[lo:]:
        if bar.open_time >= end:
            break
        stop_hit = bar.low <= trade["stop"] if side == "LONG" else bar.high >= trade["stop"]
        target_hit = bar.high >= trade["target"] if side == "LONG" else bar.low <= trade["target"]
        if stop_hit or target_hit:
            price = trade["stop"] if stop_hit else trade["target"]
            gross = price - trade["entry"] if side == "LONG" else trade["entry"] - price
            trade["exit"] = price
            trade["exit_time"] = bar.open_time
            trade["exit_reason"] = "STOP" if stop_hit else "TARGET"
            trade["net_pnl"] = gross - (trade["entry"] + price) * 0.0002
            trade["r_multiple"] = trade["net_pnl"] / trade["risk"]
            return trade
        if not trade["trail"]:
            continue
        if side == "LONG":
            best = max(best, bar.high)
            if best >= trade["arm"]:
                armed = True
            if armed:
                floor = trade["entry"] * 1.0004
                trade["stop"] = max(trade["stop"], best - trade["atr"], floor)
        else:
            best = min(best, bar.low)
            if best <= trade["arm"]:
                armed = True
            if armed:
                floor = trade["entry"] * 0.9996
                trade["stop"] = min(trade["stop"], best + trade["atr"], floor)
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
    return {"db": name, "combined": _bucket(trades), "by_side": {side: _bucket([t for t in trades if t["side"] == side]) for side in ("LONG", "SHORT")}}


if __name__ == "__main__":
    main()
