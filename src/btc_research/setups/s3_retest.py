"""S3 breakout and retest. Structure only. The 25 bp stop floor is the S1 cost result, not a new signal."""

from __future__ import annotations

from btc_research.features import atr
from btc_research.structure import swing_points


def run_s3(bars_1m, bars_5m, bars_15m, cfg, sides):
    left, right = int(cfg["pivot_left"]), int(cfg["pivot_right"])
    highs, lows = swing_points([b.high for b in bars_15m], [b.low for b in bars_15m], left, right)
    atr_15 = atr([b.high for b in bars_15m], [b.low for b in bars_15m], [b.close for b in bars_15m], int(cfg["atr_period"]))
    min_stop = float(cfg.get("min_stop_bps", 25)) / 10_000.0
    skips, trades, next_free, i1, armed = {}, [], 0, 0, None
    for i15, bar in enumerate(bars_15m):
        now = bar.close_time
        if now < next_free:
            continue
        if armed is None:
            armed = _breakout(bar, highs, lows, i15, sides)
            if armed is None:
                _skip(skips, "NO_BREAK")
            continue
        if i15 > armed["expire_index"]:
            _skip(skips, "RETEST_EXPIRED")
            armed = None
            continue
        if not _retest_holds(armed, bar):
            continue
        atr_m = atr_15[i15]
        if not atr_m:
            _skip(skips, "ATR_NOT_READY")
            armed = None
            continue
        extreme = bar.low if armed["side"] == "LONG" else bar.high
        stop = extreme - float(cfg["atr_buffer"]) * atr_m if armed["side"] == "LONG" else extreme + float(cfg["atr_buffer"]) * atr_m
        while i1 < len(bars_1m) and bars_1m[i1].open_time < now:
            i1 += 1
        if i1 >= len(bars_1m):
            _skip(skips, "NO_ENTRY_BAR")
            armed = None
            continue
        entry = bars_1m[i1]
        fill = _slip(entry.open, armed["side"], cfg, True)
        risk = (fill - stop) if armed["side"] == "LONG" else (stop - fill)
        if risk <= 0 or risk / fill < min_stop:
            _skip(skips, "STOP_TOO_TIGHT")
            armed = None
            continue
        moved = (entry.open - bar.close) if armed["side"] == "LONG" else (bar.close - entry.open)
        if moved > float(cfg["too_late_r"]) * risk:
            _skip(skips, "TOO_LATE")
            armed = None
            continue
        target = fill + float(cfg["target_r"]) * risk if armed["side"] == "LONG" else fill - float(cfg["target_r"]) * risk
        trade = _simulate(bars_1m, i1, armed["side"], fill, stop, target, cfg)
        trade.update({"family": "S3", "side": armed["side"], "decision_time": now, "entry_time": entry.open_time, "invalidation": extreme, "reason": "S3_BREAK_RETEST"})
        trades.append(trade)
        next_free = trade["exit_time"]
        armed = None
    return trades, skips


def _breakout(bar, highs, lows, i15, sides):
    prior_highs = [p for p in highs if p.confirm_index < i15]
    prior_lows = [p for p in lows if p.confirm_index < i15]
    if "LONG" in sides and prior_highs and bar.close > prior_highs[-1].price:
        return {"side": "LONG", "level": prior_highs[-1].price, "expire_index": i15 + 6}
    if "SHORT" in sides and prior_lows and bar.close < prior_lows[-1].price:
        return {"side": "SHORT", "level": prior_lows[-1].price, "expire_index": i15 + 6}
    return None


def _retest_holds(armed, bar):
    if armed["side"] == "LONG":
        return bar.low <= armed["level"] and bar.close > armed["level"]
    return bar.high >= armed["level"] and bar.close < armed["level"]


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
