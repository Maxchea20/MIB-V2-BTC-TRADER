"""Floors and the eye for an open Hunt trade. Stop 1.5 ATR and target 2.5 ATR stay as they are.

A floor is a stop that moves up once the trade is in profit. The eye is an early exit that
looks at closed 15m candles and at the 15m candle still forming. Stateless: every call walks the
1m bars again from the entry, so it can be called as often as the backtest needs.
"""

from __future__ import annotations


MODES = {
    # floor at +1R once the best price is 1.75 ATR, floor at +2.0 ATR once it is 2.25 ATR
    "floors": dict(tiers=((1.75, 1.5), (2.25, 2.0))),
    # floors with no cushion, plus the eye from 1.5 ATR on
    "eye2": dict(tiers=((1.5, 1.5), (2.0, 2.0)), arm=1.5, closed=True, forming=True, pb=0.2),
}
FIFTEEN = 900_000


def _sell_candle(c, min_span):
    span = c["hi"] - c["lo"]
    if span <= 0 or (min_span is not None and span < min_span):
        return False
    return abs(c["cl"] - c["op"]) / span >= 0.5 and c["cl"] < c["op"] and c["cl"] <= c["lo"] + span / 3


def _closed_fires(candles, last_high_idx):
    c = candles[-1]
    struct = len(candles) >= 4 and c["cl"] < min(x["lo"] for x in candles[-4:-1])
    stall = len(candles) - 1 - last_high_idx >= 4
    return struct or stall or _sell_candle(c, None)


def walk(trade, bars, start, end, mode):
    """Walk the 1m bars from `start`. Returns the trade with exit fields set, or None if still open at `end`."""
    cfg = MODES[mode]
    sign = 1 if trade["side"] == "LONG" else -1
    entry, stop, target = trade["entry"], trade["stop"], trade["target"]
    atr = trade["atr"]
    e = sign * entry
    base_stop = sign * stop
    stop_p = base_stop
    target_p = sign * target
    best = e
    candles, cur = [], None
    last_high_idx = 0
    pending = False
    arm = cfg.get("arm")
    lo_i = _first(bars, start)
    for bar in bars[lo_i:]:
        if bar.open_time >= end:
            return None
        hi = bar.high if sign == 1 else -bar.low
        lo = bar.low if sign == 1 else -bar.high
        op, cl = sign * bar.open, sign * bar.close
        key = bar.open_time // FIFTEEN
        if cur is not None and cur["key"] != key:
            candles.append(cur)
            cur = None
            if arm is not None and best >= e + arm * atr and cfg.get("closed") and _closed_fires(candles, last_high_idx):
                pending = True
        if cur is None:
            cur = {"key": key, "op": op, "hi": hi, "lo": lo, "cl": cl}
        else:
            cur["hi"], cur["lo"], cur["cl"] = max(cur["hi"], hi), min(cur["lo"], lo), cl
        if pending:
            return _close(trade, sign * op, bar.open_time, "EYE")
        if lo <= stop_p:
            return _close(trade, sign * stop_p, bar.open_time, "FLOOR" if stop_p > base_stop else "STOP")
        if hi >= target_p:
            return _close(trade, target, bar.open_time, "TARGET")
        if hi > best:
            best = hi
            last_high_idx = len(candles)
        for arm_level, floor_level in cfg["tiers"]:
            if best >= e + arm_level * atr:
                stop_p = max(stop_p, e + floor_level * atr)
        if arm is not None and best >= e + arm * atr and cfg.get("forming"):
            if best - cl >= cfg["pb"] * atr or _sell_candle(cur, 0.5 * atr):
                pending = True
    return None


def _first(bars, start):
    lo, hi = 0, len(bars)
    while lo < hi:
        mid = (lo + hi) // 2
        if bars[mid].open_time < start:
            lo = mid + 1
        else:
            hi = mid
    return lo


def _close(trade, price, exit_time, reason):
    side = trade["side"]
    gross = price - trade["entry"] if side == "LONG" else trade["entry"] - price
    trade["exit"] = price
    trade["exit_time"] = exit_time
    trade["exit_reason"] = reason
    trade["net_pnl"] = gross - (trade["entry"] + price) * 0.0002
    trade["r_multiple"] = trade["net_pnl"] / trade["risk"]
    return trade
