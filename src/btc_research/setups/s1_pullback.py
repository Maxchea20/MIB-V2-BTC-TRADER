"""S1 pullback continuation, causal. Structure only."""

from __future__ import annotations

from btc_research.features import atr
from btc_research.structure import swing_points, visible


def run_s1(bars_1m, bars_5m, bars_15m, bars_1h, cfg, sides):
    left, right, period = int(cfg["pivot_left"]), int(cfg["pivot_right"]), int(cfg["atr_period"])
    h1_highs, h1_lows = swing_points([b.high for b in bars_1h], [b.low for b in bars_1h], left, right)
    m15_highs, m15_lows = swing_points([b.high for b in bars_15m], [b.low for b in bars_15m], left, right)
    m5_highs, m5_lows = swing_points([b.high for b in bars_5m], [b.low for b in bars_5m], left, right)
    atr_1h = atr([b.high for b in bars_1h], [b.low for b in bars_1h], [b.close for b in bars_1h], period)
    atr_15 = atr([b.high for b in bars_15m], [b.low for b in bars_15m], [b.close for b in bars_15m], period)
    skips, trades, next_free, i1 = {}, [], 0, 0
    stop_scale = float(cfg.get("stop_scale", 1.0))
    for i5, bar in enumerate(bars_5m):
        now = bar.close_time
        if now < next_free:
            continue
        side = _bias(bars_1h, h1_highs, h1_lows, now)
        if side is None or side not in sides:
            _skip(skips, "NO_BIAS" if side is None else "SIDE_FILTER")
            continue
        setup = _pullback(side, bars_1h, h1_highs, h1_lows, bars_15m, m15_highs, m15_lows, now)
        if setup is None:
            _skip(skips, "NO_PULLBACK_HOLD")
            continue
        if not _reclaim(side, bars_5m, m5_highs, m5_lows, i5, setup["pullback_confirm_time"]):
            _skip(skips, "NO_5M_RECLAIM")
            continue
        atr_h = _latest(bars_1h, atr_1h, now)
        atr_m = _latest(bars_15m, atr_15, now)
        if not atr_h or not atr_m:
            _skip(skips, "ATR_NOT_READY")
            continue
        extension = (bar.close - setup["origin"]) / atr_h if side == "LONG" else (setup["origin"] - bar.close) / atr_h
        if extension > float(cfg["extension_cap_atr"]):
            _skip(skips, "EXTENSION")
            continue
        structure_stop = setup["invalidation"] - float(cfg["atr_buffer"]) * atr_m if side == "LONG" else setup["invalidation"] + float(cfg["atr_buffer"]) * atr_m
        while i1 < len(bars_1m) and bars_1m[i1].open_time < now:
            i1 += 1
        if i1 >= len(bars_1m):
            _skip(skips, "NO_ENTRY_BAR")
            continue
        entry_bar = bars_1m[i1]
        risk = (bar.close - structure_stop) if side == "LONG" else (structure_stop - bar.close)
        if risk <= 0:
            _skip(skips, "INVALID_STOP")
            continue
        moved = (entry_bar.open - bar.close) if side == "LONG" else (bar.close - entry_bar.open)
        if moved > float(cfg["too_late_r"]) * risk:
            _skip(skips, "TOO_LATE")
            continue
        fill = _slip(entry_bar.open, side, cfg, True)
        risk_fill = (fill - structure_stop) if side == "LONG" else (structure_stop - fill)
        if risk_fill <= 0:
            _skip(skips, "INVALID_STOP_AFTER_SLIPPAGE")
            continue
        stop = fill - stop_scale * risk_fill if side == "LONG" else fill + stop_scale * risk_fill
        target = fill + float(cfg["target_r"]) * risk_fill if side == "LONG" else fill - float(cfg["target_r"]) * risk_fill
        trade = _simulate(bars_1m, i1, side, fill, stop, target, cfg)
        trade.update({"family": "S1", "side": side, "decision_time": now, "entry_time": entry_bar.open_time, "extension_atr": extension, "atr_1h": atr_h, "atr_15m": atr_m, "invalidation": setup["invalidation"], "reason": "S1_5M_RECLAIM"})
        trades.append(trade)
        next_free = trade["exit_time"]
    return trades, skips


def _skip(skips, key):
    skips[key] = skips.get(key, 0) + 1


def _bias(bars, highs, lows, now):
    idx = _last(bars, now)
    if idx < 0:
        return None
    vh, vl = visible(highs, idx), visible(lows, idx)
    if len(vh) < 2 or len(vl) < 2:
        return None
    hh = vh[-1].price > vh[-2].price and vl[-1].price > vl[-2].price
    ll = vh[-1].price < vh[-2].price and vl[-1].price < vl[-2].price
    if hh and not ll:
        return "LONG"
    if ll and not hh:
        return "SHORT"
    return None


def _pullback(side, bars_1h, h1_highs, h1_lows, bars_15m, m15_highs, m15_lows, now):
    i1, i15 = _last(bars_1h, now), _last(bars_15m, now)
    vh, vl = visible(h1_highs, i1), visible(h1_lows, i1)
    if not vh or not vl:
        return None
    if side == "LONG":
        pivots = [p for p in visible(m15_lows, i15) if p.price > vl[-1].price and bars_15m[p.index].open_time >= bars_1h[vl[-1].index].open_time]
        if not pivots or pivots[-1].price >= vh[-1].price:
            return None
        return {"invalidation": vl[-1].price, "origin": vl[-1].price, "pullback_confirm_time": bars_15m[pivots[-1].confirm_index].close_time}
    pivots = [p for p in visible(m15_highs, i15) if p.price < vh[-1].price and bars_15m[p.index].open_time >= bars_1h[vh[-1].index].open_time]
    if not pivots or pivots[-1].price <= vl[-1].price:
        return None
    return {"invalidation": vh[-1].price, "origin": vh[-1].price, "pullback_confirm_time": bars_15m[pivots[-1].confirm_index].close_time}


def _reclaim(side, bars_5m, highs, lows, i5, pullback_confirm_time):
    if bars_5m[i5].close_time < pullback_confirm_time:
        return False
    pivots = highs if side == "LONG" else lows
    formed = [p for p in pivots if p.confirm_index <= i5 and bars_5m[p.index].close_time >= pullback_confirm_time]
    if not formed:
        return False
    return bars_5m[i5].close > formed[-1].price if side == "LONG" else bars_5m[i5].close < formed[-1].price


def _latest(bars, values, now):
    idx = _last(bars, now)
    return None if idx < 0 else values[idx]


def _last(bars, now):
    lo, hi, ans = 0, len(bars) - 1, -1
    while lo <= hi:
        mid = (lo + hi) // 2
        if bars[mid].close_time <= now:
            ans = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return ans


def _slip(price, side, cfg, is_entry):
    tick = float(cfg["tick_size"]) * int(cfg["slippage_ticks"])
    bps = float(cfg["slippage_bps"]) / 10_000.0
    worse_up = side == "LONG" if is_entry else side == "SHORT"
    return price * (1 + bps) + tick if worse_up else price * (1 - bps) - tick


def _simulate(bars, entry_index, side, fill, stop, target, cfg):
    fee_rate = float(cfg["fee_bps_per_side"]) / 10_000.0
    mfe = mae = 0.0
    risk = abs(fill - stop)
    exit_price, exit_time, reason = fill, bars[entry_index].close_time, "END_OF_DATA"
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
            exit_price, exit_time, reason = _slip(stop, side, cfg, False), bar.close_time, "STOP_SAME_BAR" if hit_target else "STOP"
            break
        if hit_target:
            exit_price, exit_time, reason = _slip(target, side, cfg, False), bar.close_time, "TARGET"
            break
        exit_price, exit_time = bar.close, bar.close_time
    gross = (exit_price - fill) if side == "LONG" else (fill - exit_price)
    fees = fee_rate * fill + fee_rate * abs(exit_price)
    return {"entry": fill, "stop": stop, "target": target, "exit": exit_price, "exit_time": exit_time, "exit_reason": reason, "gross_pnl": gross, "fees": fees, "slippage_pnl": 0.0, "funding_pnl": 0.0, "net_pnl": gross - fees, "r_multiple": (gross - fees) / risk if risk else 0.0, "mfe_r": mfe, "mae_r": mae, "hold_seconds": max(0, (exit_time - bars[entry_index].open_time) / 1000), "notional": fill}
