"""S4 range fade. Structure only. Target is the range midpoint, not a fixed R multiple."""

from __future__ import annotations

from btc_research.features import atr
from btc_research.structure import swing_points


def run_s4(bars_1m, bars_15m, cfg, sides):
    left, right = int(cfg["pivot_left"]), int(cfg["pivot_right"])
    highs, lows = swing_points([b.high for b in bars_15m], [b.low for b in bars_15m], left, right)
    atr_15 = atr([b.high for b in bars_15m], [b.low for b in bars_15m], [b.close for b in bars_15m], int(cfg["atr_period"]))
    min_stop = float(cfg.get("min_stop_bps", 25)) / 10_000.0
    skips, trades, next_free, i1 = {}, [], 0, 0
    for i15, bar in enumerate(bars_15m):
        now = bar.close_time
        if now < next_free:
            continue
        setup = _fade(bar, highs, lows, i15, sides)
        if setup is None:
            _skip(skips, "NO_RANGE_REJECTION")
            continue
        atr_m = atr_15[i15]
        if not atr_m:
            _skip(skips, "ATR_NOT_READY")
            continue
        side, extreme, midpoint = setup
        stop = extreme - float(cfg["atr_buffer"]) * atr_m if side == "LONG" else extreme + float(cfg["atr_buffer"]) * atr_m
        while i1 < len(bars_1m) and bars_1m[i1].open_time < now:
            i1 += 1
        if i1 >= len(bars_1m):
            _skip(skips, "NO_ENTRY_BAR")
            continue
        entry = bars_1m[i1]
        fill = _slip(entry.open, side, cfg, True)
        risk = (fill - stop) if side == "LONG" else (stop - fill)
        reward = (midpoint - fill) if side == "LONG" else (fill - midpoint)
        if risk <= 0 or risk / fill < min_stop or reward < risk:
            _skip(skips, "STOP_OR_REWARD_TOO_SMALL")
            continue
        trade = _simulate(bars_1m, i1, side, fill, stop, midpoint, cfg)
        trade.update({"family": "S4", "side": side, "decision_time": now, "entry_time": entry.open_time, "invalidation": extreme, "reason": "S4_RANGE_FADE"})
        trades.append(trade)
        next_free = trade["exit_time"]
    return trades, skips


def _fade(bar, highs, lows, i15, sides):
    prior_highs = [p for p in highs if p.confirm_index < i15]
    prior_lows = [p for p in lows if p.confirm_index < i15]
    if not prior_highs or not prior_lows:
        return None
    top, bottom = prior_highs[-1].price, prior_lows[-1].price
    if top <= bottom:
        return None
    midpoint = (top + bottom) / 2
    if "LONG" in sides and bar.low < bottom < bar.close < midpoint:
        return "LONG", bar.low, midpoint
    if "SHORT" in sides and bar.high > top > bar.close > midpoint:
        return "SHORT", bar.high, midpoint
    return None


def _slip(price, side, cfg, is_entry):
    tick = float(cfg["tick_size"]) * int(cfg["slippage_ticks"])
    bps = float(cfg["slippage_bps"]) / 10_000.0
    worse_up = side == "LONG" if is_entry else side == "SHORT"
    return price * (1 + bps) + tick if worse_up else price * (1 - bps) - tick


def _simulate(bars, entry_index, side, fill, stop, target, cfg):
    fee_rate = float(cfg["fee_bps_per_side"]) / 10_000.0
    risk = abs(fill - stop)
    exit_price, exit_time, reason = fill, bars[entry_index].close_time, "END_OF_DATA"
    mfe = mae = 0.0
    for bar in bars[entry_index:]:
        if side == "LONG":
            mfe = max(mfe, (bar.high - fill) / risk)
            mae = min(mae, (bar.low - fill) / risk)
            hit_stop, hit_target = bar.low <= stop, bar.high >= target
        else:
            mfe = max(mfe, (fill - bar.low) / risk)
            mae = min(mae, (fill - bar.high) / risk)
            hit_stop, hit_target = bar.high >= stop, bar.low <= target
        if hit_stop:
            exit_price = _slip(stop, side, cfg, False)
            exit_time = bar.close_time
            reason = "STOP_SAME_BAR" if hit_target else "STOP"
            break
        if hit_target:
            exit_price = _slip(target, side, cfg, False)
            exit_time = bar.close_time
            reason = "TARGET"
            break
        exit_price, exit_time = bar.close, bar.close_time
    gross = (exit_price - fill) if side == "LONG" else (fill - exit_price)
    fees = fee_rate * fill + fee_rate * abs(exit_price)
    return {"entry": fill, "stop": stop, "target": target, "exit": exit_price, "exit_time": exit_time, "exit_reason": reason, "gross_pnl": gross, "fees": fees, "slippage_pnl": 0.0, "funding_pnl": 0.0, "net_pnl": gross - fees, "r_multiple": (gross - fees) / risk if risk else 0.0, "mfe_r": mfe, "mae_r": mae, "hold_seconds": max(0, (exit_time - bars[entry_index].open_time) / 1000), "notional": fill}


def _skip(skips, key):
    skips[key] = skips.get(key, 0) + 1
