"""W1 swing pullback. 1D regime, 4H hold, 1H reclaim, next 15M open. Structure only."""

from __future__ import annotations

from btc_research.features import atr
from btc_research.structure import swing_points


def run_w1(bars_1m, bars_15m, bars_1h, bars_4h, bars_1d, cfg, sides):
    left, right = int(cfg["pivot_left"]), int(cfg["pivot_right"])
    d_highs, d_lows = swing_points([b.high for b in bars_1d], [b.low for b in bars_1d], left, right)
    h4_highs, h4_lows = swing_points([b.high for b in bars_4h], [b.low for b in bars_4h], left, right)
    h1_highs, h1_lows = swing_points([b.high for b in bars_1h], [b.low for b in bars_1h], left, right)
    atr_4h = atr([b.high for b in bars_4h], [b.low for b in bars_4h], [b.close for b in bars_4h], int(cfg["atr_period"]))
    atr_1d = atr([b.high for b in bars_1d], [b.low for b in bars_1d], [b.close for b in bars_1d], int(cfg["atr_period"]))
    min_stop = float(cfg.get("min_stop_bps", 25)) / 10_000.0
    skips, trades, next_free, i1 = {}, [], 0, 0
    for i1h, bar in enumerate(bars_1h):
        now = bar.close_time
        if now < next_free:
            continue
        side = _daily_bias(bars_1d, d_highs, d_lows, now)
        if side not in sides:
            _skip(skips, "NO_DAILY_BIAS")
            continue
        held = _four_hour_hold(side, bars_4h, h4_highs, h4_lows, now)
        if held is None:
            _skip(skips, "NO_4H_HOLD")
            continue
        if not _hour_reclaim(side, bars_1h, h1_highs, h1_lows, i1h, held["confirm_time"]):
            _skip(skips, "NO_1H_RECLAIM")
            continue
        i4 = _last(bars_4h, now)
        iday = _last(bars_1d, now)
        if i4 < 0 or iday < 0 or not atr_4h[i4] or not atr_1d[iday]:
            _skip(skips, "ATR_NOT_READY")
            continue
        extension = (bar.close - held["origin"]) / atr_1d[iday] if side == "LONG" else (held["origin"] - bar.close) / atr_1d[iday]
        if extension > float(cfg["extension_cap_atr"]):
            _skip(skips, "EXTENSION")
            continue
        stop = held["invalidation"] - float(cfg["atr_buffer"]) * atr_4h[i4] if side == "LONG" else held["invalidation"] + float(cfg["atr_buffer"]) * atr_4h[i4]
        while i1 < len(bars_1m) and bars_1m[i1].open_time < now:
            i1 += 1
        if i1 >= len(bars_1m):
            _skip(skips, "NO_ENTRY_BAR")
            continue
        entry = bars_1m[i1]
        fill = _slip(entry.open, side, cfg, True)
        risk = (fill - stop) if side == "LONG" else (stop - fill)
        if risk <= 0 or risk / fill < min_stop:
            _skip(skips, "STOP_TOO_TIGHT")
            continue
        moved = (entry.open - bar.close) if side == "LONG" else (bar.close - entry.open)
        if moved > float(cfg["too_late_r"]) * risk:
            _skip(skips, "TOO_LATE")
            continue
        target = fill + float(cfg["target_r"]) * risk if side == "LONG" else fill - float(cfg["target_r"]) * risk
        trade = _simulate(bars_1m, i1, side, fill, stop, target, cfg)
        trade.update({"family": "W1", "side": side, "decision_time": now, "entry_time": entry.open_time, "invalidation": held["invalidation"], "reason": "W1_SWING_PULLBACK"})
        trades.append(trade)
        next_free = trade["exit_time"]
    return trades, skips


def _daily_bias(bars, highs, lows, now):
    idx = _last(bars, now)
    if idx < 0:
        return None
    vh = [p for p in highs if p.confirm_index <= idx]
    vl = [p for p in lows if p.confirm_index <= idx]
    if len(vh) < 2 or len(vl) < 2:
        return None
    if vh[-1].price > vh[-2].price and vl[-1].price > vl[-2].price:
        return "LONG"
    if vh[-1].price < vh[-2].price and vl[-1].price < vl[-2].price:
        return "SHORT"
    return None


def _four_hour_hold(side, bars, highs, lows, now):
    idx = _last(bars, now)
    if idx < 0:
        return None
    if side == "LONG":
        pivots = [p for p in lows if p.confirm_index <= idx]
        if len(pivots) < 2 or pivots[-1].price <= pivots[-2].price:
            return None
        return {"invalidation": pivots[-1].price, "origin": pivots[-2].price, "confirm_time": bars[pivots[-1].confirm_index].close_time}
    pivots = [p for p in highs if p.confirm_index <= idx]
    if len(pivots) < 2 or pivots[-1].price >= pivots[-2].price:
        return None
    return {"invalidation": pivots[-1].price, "origin": pivots[-2].price, "confirm_time": bars[pivots[-1].confirm_index].close_time}


def _hour_reclaim(side, bars, highs, lows, i1h, confirm_time):
    if bars[i1h].close_time < confirm_time:
        return False
    if side == "LONG":
        pivots = [p for p in highs if p.confirm_index <= i1h and bars[p.index].close_time >= confirm_time]
        return bool(pivots) and bars[i1h].close > pivots[-1].price
    pivots = [p for p in lows if p.confirm_index <= i1h and bars[p.index].close_time >= confirm_time]
    return bool(pivots) and bars[i1h].close < pivots[-1].price


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
