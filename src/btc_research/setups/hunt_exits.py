"""Floors and the eye for an open Hunt trade. Stop 1.5 ATR and target 2.5 ATR stay as they are.

A floor is a stop that moves up once the trade is in profit. The eye is an early exit that
looks at closed 15m candles and at the 15m candle still forming. Stateless: every call walks the
1m bars again from the entry, so it can be called as often as the backtest needs.
"""

from __future__ import annotations

from btc_research.execution.simulator import resolve_bar, slippage


MODES = {
    # floor at +1R once the best price is 1.75 ATR, floor at +2.0 ATR once it is 2.25 ATR
    "floors": dict(tiers=((1.75, 1.5), (2.25, 2.0))),
    # floors with no cushion, plus the eye from 1.5 ATR on
    "eye2": dict(tiers=((1.5, 1.5), (2.0, 2.0)), arm=1.5, closed=True, forming=True, pb=0.2),
}
# Options for a mode dict passed to walk(): notarget=True removes the 2.5 ATR target;
# trail=(arm_atr, dist_atr) trails the best price by dist_atr once it is arm_atr in favor.
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


def walk(trade, bars, start, end, mode, exec_cfg=None):
    """Walk the 1m bars from `start`. Returns the trade with exit fields set, or None if still open at `end`.
    exec_cfg None: the legacy idealised exits (exact stop/target price, no slippage, no latency). Kept so old numbers can be reproduced.
    exec_cfg given: the strategy decisions (when a floor moves, when the eye fires) are unchanged, but every exit is filled by the execution
    simulator: resting stop-market and take-profit orders only exist from fill + latency, gaps fill at the open, slippage is added, a take-profit
    needs a trade-through, and a stop and a target in the same 1m bar follow exec_cfg.intrabar_policy."""
    cfg = mode if isinstance(mode, dict) else MODES[mode]
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
    active_time = start + exec_cfg.latency_ms if exec_cfg is not None else None
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
            if exec_cfg is not None:
                raw = sign * op
                return _close_exec(trade, "EYE", raw, raw - sign * slippage(raw, exec_cfg, False), bar.open_time, "MARKET", "taker", exec_cfg)
            return _close(trade, sign * op, bar.open_time, "EYE")
        if exec_cfg is None:
            if lo <= stop_p:
                return _close(trade, sign * stop_p, bar.open_time, "FLOOR" if stop_p > base_stop else "STOP")
            if not cfg.get("notarget") and hi >= target_p:
                return _close(trade, target, bar.open_time, "TARGET")
        elif bar.open_time >= active_time:
            ev = resolve_bar(bar, trade["side"], sign * stop_p, None if cfg.get("notarget") else target, exec_cfg)
            if ev is not None:
                reason = ev["reason"]
                if reason == "STOP" and stop_p > base_stop:
                    reason = "FLOOR"
                return _close_exec(trade, reason, ev["raw"], ev["fill"], ev["time"], ev["order_type"], ev["liquidity"], exec_cfg)
        if hi > best:
            best = hi
            last_high_idx = len(candles)
        trail = cfg.get("trail")
        if trail and best >= e + trail[0] * atr:
            stop_p = max(stop_p, best - trail[1] * atr)
        for arm_level, floor_level in cfg["tiers"]:
            if best >= e + arm_level * atr:
                stop_p = max(stop_p, e + floor_level * atr)
        if arm is not None and best >= e + arm * atr and cfg.get("forming"):
            if best - cl >= cfg["pb"] * atr or _sell_candle(cur, 0.5 * atr):
                pending = True
    return None


def _close_exec(trade, reason, raw, fill, exit_time, order_type, liquidity, cfg):
    """Book an exit that the execution simulator filled. R stays net PnL / the planned risk, so an exit worse than the stop shows as worse than -1R."""
    trade["exit_time"] = exit_time
    trade["exit_reason"] = reason
    trade["exit_order_type"] = order_type
    trade["exit_liquidity"] = liquidity
    if reason == "UNRESOLVED_BOTH_HIT":
        trade.update({"exit": None, "exit_raw": None, "exit_slippage": None, "fees": None, "net_pnl": None, "r_multiple": None, "gross_r_before_costs": None})
        return trade
    sign = 1 if trade["side"] == "LONG" else -1
    fees = (trade["entry"] + fill) * cfg.fee_bps_per_side / 10_000.0
    trade["exit"] = fill
    trade["exit_raw"] = raw
    trade["exit_slippage"] = abs(fill - raw)
    trade["fees"] = fees
    trade["net_pnl"] = sign * (fill - trade["entry"]) - fees
    trade["r_multiple"] = trade["net_pnl"] / trade["risk"]
    trade["gross_r_before_costs"] = sign * (raw - trade.get("entry_raw", trade["entry"])) / trade["risk"]
    return trade


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
