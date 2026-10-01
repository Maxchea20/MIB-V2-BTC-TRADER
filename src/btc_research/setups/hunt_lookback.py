"""20-bar 15m sign, 50-bar 5m break.

trend_filter skips longs in a down close and shorts in an up close.
"""

from __future__ import annotations


def run_hunt20(bars_1m, bars_5m, bars_15m, cfg, sides):
    lookback_15 = int(cfg.get("lookback_15", 20))
    lookback_5 = int(cfg.get("lookback_5", 50))
    period = int(cfg.get("atr_period", 14))
    sl_atr = float(cfg.get("sl_atr", 1.5))
    tp_atr = float(cfg.get("tp_atr", 2.5))
    quiet_ms = int(cfg.get("quiet_minutes", 15)) * 60_000
    reverse = cfg.get("exit_mode") == "reverse"
    mode = cfg.get("entry_mode", "break")
    wait_bars = int(cfg.get("pullback_wait_bars", 6))
    trend_on = bool(cfg.get("trend_filter", False))
    trend_bars = int(cfg.get("trend_days", 20)) * 96
    atr_15 = _atr(bars_15m, period)

    skips, trades = {}, []
    next_free = 0
    bias = None
    for i, bar in enumerate(bars_5m):
        now = bar.close_time
        if now < next_free:
            continue
        if i < lookback_5:
            _skip(skips, "WARMUP")
            continue
        window = bars_5m[i - lookback_5:i]
        prior_high = max(b.high for b in window)
        prior_low = min(b.low for b in window)
        side = event = level = None
        if bar.close > prior_high:
            side, event, level = "LONG", ("BOS" if bias == "LONG" else "CHoCH"), prior_high
        elif bar.close < prior_low:
            side, event, level = "SHORT", ("BOS" if bias == "SHORT" else "CHoCH"), prior_low
        if side is None:
            _skip(skips, "NO_5M_BREAK")
            continue
        bias = side
        if side not in sides:
            _skip(skips, "SIDE_FILTER")
            continue
        sign = _sign(bars_15m, now, lookback_15)
        if sign is None:
            _skip(skips, "NO_15M_SIGN")
            continue
        if sign != side:
            _skip(skips, "SIGN_MISMATCH")
            continue
        trend = _trend(bars_15m, now, trend_bars) if trend_on else "NONE"
        if trend == "DOWN" and side == "LONG":
            _skip(skips, "TREND_DOWN")
            continue
        if trend == "UP" and side == "SHORT":
            _skip(skips, "TREND_UP")
            continue

        use_later = mode == "later_pullback" or (mode == "split_short_pullback" and side == "SHORT")
        if mode == "engulf_5m":
            if i == 0 or not _engulf(bars_5m[i - 1], bar, side):
                _skip(skips, "NO_ENGULF")
                continue
            nxt = _next_open(bars_1m, now)
            if nxt is None:
                _skip(skips, "NO_ENTRY_BAR")
                continue
            i_fill, raw = nxt
            if side == "LONG" and raw < level:
                _skip(skips, "OPEN_NOT_THROUGH")
                continue
            if side == "SHORT" and raw > level:
                _skip(skips, "OPEN_NOT_THROUGH")
                continue
        elif use_later:
            found = _later_touch(bars_1m, bars_5m, i, side, level, wait_bars)
            if found is None:
                _skip(skips, "NO_LATER_PULLBACK")
                continue
            fill_bar, i_fill, raw = found
            now = fill_bar.close_time
        else:
            tapped = bar.low <= level <= bar.close if side == "LONG" else bar.close <= level <= bar.high
            if not tapped:
                _skip(skips, "NO_PULLBACK_TAP")
                continue
            hit = _touch(bars_1m, bar.open_time, now, side, level)
            if hit is None:
                _skip(skips, "NO_LIMIT_TOUCH")
                continue
            i_fill, raw = hit

        atr_v = _latest_atr(bars_15m, atr_15, now)
        if not atr_v:
            _skip(skips, "ATR_NOT_READY")
            continue
        entry = _slip(raw, side, cfg, True)
        risk = sl_atr * atr_v
        if risk <= 0:
            _skip(skips, "INVALID_STOP")
            continue
        if reverse:
            trade = _to_reverse(bars_1m, bars_5m, i, i_fill, side, entry, risk, lookback_5, cfg)
        else:
            stop = entry - risk if side == "LONG" else entry + risk
            target = entry + tp_atr * atr_v if side == "LONG" else entry - tp_atr * atr_v
            trade = _simulate(bars_1m, i_fill, side, entry, stop, target, risk, cfg)
        trade.update({"family": "HUNT20", "side": side, "decision_time": now, "entry_time": bars_1m[i_fill].open_time, "reason": "engulf_5m" if mode == "engulf_5m" else ("later_pullback" if use_later else "pullback_tap"), "gate": "fresh", "event": event, "slot": ((bar.open_time % 900_000) // 300_000) + 1, "thesis_level": level, "invalidation": prior_low if side == "LONG" else prior_high, "atr_15m": atr_v, "weather": trend})
        trades.append(trade)
        next_free = trade["exit_time"] + quiet_ms
    return trades, skips


def _trend(bars, now, lookback):
    closed = [b for b in bars if b.close_time <= now]
    if len(closed) <= lookback:
        return "NONE"
    if closed[-1].close < closed[-1 - lookback].close:
        return "DOWN"
    if closed[-1].close > closed[-1 - lookback].close:
        return "UP"
    return "NONE"


def _engulf(prior, bar, side):
    if side == "LONG":
        return bar.close > bar.open and prior.close < prior.open and bar.open <= prior.close and bar.close >= prior.open
    return bar.close < bar.open and prior.close > prior.open and bar.open >= prior.close and bar.close <= prior.open


def _later_touch(bars_1m, bars_5m, i_signal, side, level, wait_bars):
    last = min(len(bars_5m), i_signal + 1 + wait_bars)
    for j in range(i_signal + 1, last):
        bar = bars_5m[j]
        came_back = bar.low <= level if side == "LONG" else bar.high >= level
        if not came_back:
            continue
        hit = _touch(bars_1m, bar.open_time, bar.close_time, side, level)
        if hit is None:
            continue
        return bar, hit[0], hit[1]
    return None


def _to_reverse(bars_1m, bars_5m, i_signal, i_fill, side, entry, risk, lookback, cfg):
    exit_i = None
    exit_raw = None
    reason = "END_OF_DATA"
    for j in range(i_signal + 1, len(bars_5m)):
        bar = bars_5m[j]
        if j < lookback:
            continue
        window = bars_5m[j - lookback:j]
        flipped = side == "LONG" and bar.close < min(b.low for b in window)
        flipped = flipped or (side == "SHORT" and bar.close > max(b.high for b in window))
        if not flipped:
            continue
        nxt = _next_open(bars_1m, bar.close_time)
        if nxt is None:
            break
        exit_i, exit_raw = nxt
        reason = "REVERSE"
        break
    if exit_raw is None:
        exit_i = len(bars_1m) - 1
        exit_raw = bars_1m[-1].close
    return _hold(bars_1m, i_fill, exit_i, side, entry, exit_raw, risk, reason, cfg)


def _next_open(bars, after):
    for i, bar in enumerate(bars):
        if bar.open_time >= after:
            return i, bar.open
    return None


def _hold(bars, i0, i_exit, side, entry, exit_raw, risk, reason, cfg):
    mfe = mae = 0.0
    last = min(i_exit, len(bars) - 1)
    for bar in bars[i0:last + 1]:
        favorable = (bar.high - entry) if side == "LONG" else (entry - bar.low)
        adverse = (entry - bar.low) if side == "LONG" else (bar.high - entry)
        mfe = max(mfe, favorable / risk)
        mae = max(mae, adverse / risk)
    exit_px = _slip(exit_raw, side, cfg, False)
    gross = (exit_px - entry) if side == "LONG" else (entry - exit_px)
    fees = (entry + abs(exit_px)) * float(cfg.get("fee_bps_per_side", 2.0)) / 10_000.0
    net = gross - fees
    ref = entry - risk if side == "LONG" else entry + risk
    return {"entry": entry, "stop": ref, "target": entry, "exit": exit_px, "exit_time": bars[last].close_time, "exit_reason": reason, "gross_pnl": gross, "fees": fees, "slippage_pnl": 0.0, "funding_pnl": 0.0, "net_pnl": net, "r_multiple": net / risk, "mfe_r": mfe, "mae_r": mae, "hold_seconds": max(0, (bars[last].close_time - bars[i0].open_time) // 1000), "notional": entry}


def _sign(bars, now, lookback):
    closed = [b for b in bars if b.close_time <= now]
    if len(closed) <= lookback:
        return None
    bar = closed[-1]
    window = closed[-1 - lookback:-1]
    if bar.close > max(b.high for b in window):
        return "LONG"
    if bar.close < min(b.low for b in window):
        return "SHORT"
    return None


def _touch(bars, start, end, side, level):
    for i, bar in enumerate(bars):
        if bar.open_time < start:
            continue
        if bar.open_time >= end:
            return None
        if side == "LONG" and (bar.open >= level or bar.low <= level):
            return i, bar.open if bar.open >= level else level
        if side == "SHORT" and (bar.open <= level or bar.high >= level):
            return i, bar.open if bar.open <= level else level
    return None


def _atr(bars, period):
    out = [None] * len(bars)
    if len(bars) <= period:
        return out
    prev = bars[0].close
    trs = []
    for i, bar in enumerate(bars):
        tr = max(bar.high - bar.low, abs(bar.high - prev), abs(bar.low - prev))
        prev = bar.close
        trs.append(tr)
        if i == period:
            out[i] = sum(trs[1:period + 1]) / period
        elif i > period and out[i - 1] is not None:
            out[i] = (out[i - 1] * (period - 1) + tr) / period
    return out


def _latest_atr(bars, values, now):
    got = None
    for bar, value in zip(bars, values):
        if bar.close_time > now:
            break
        if value:
            got = value
    return got


def _simulate(bars, i0, side, entry, stop, target, risk, cfg):
    mfe = mae = 0.0
    exit_px, exit_ts, reason = entry, bars[-1].close_time, "END_OF_DATA"
    for bar in bars[i0:]:
        favorable = (bar.high - entry) if side == "LONG" else (entry - bar.low)
        adverse = (entry - bar.low) if side == "LONG" else (bar.high - entry)
        mfe = max(mfe, favorable / risk)
        mae = max(mae, adverse / risk)
        hit_stop = bar.low <= stop if side == "LONG" else bar.high >= stop
        hit_target = bar.high >= target if side == "LONG" else bar.low <= target
        if hit_stop:
            exit_px, exit_ts, reason = stop, bar.close_time, "STOP_SAME_BAR" if hit_target else "STOP"
            break
        if hit_target:
            exit_px, exit_ts, reason = target, bar.close_time, "TARGET"
            break
    else:
        exit_px = bars[-1].close
    exit_px = _slip(exit_px, side, cfg, False)
    gross = (exit_px - entry) if side == "LONG" else (entry - exit_px)
    fees = (entry + abs(exit_px)) * float(cfg.get("fee_bps_per_side", 2.0)) / 10_000.0
    net = gross - fees
    return {"entry": entry, "stop": stop, "target": target, "exit": exit_px, "exit_time": exit_ts, "exit_reason": reason, "gross_pnl": gross, "fees": fees, "slippage_pnl": 0.0, "funding_pnl": 0.0, "net_pnl": net, "r_multiple": net / risk, "mfe_r": mfe, "mae_r": mae, "hold_seconds": max(0, (exit_ts - bars[i0].open_time) // 1000), "notional": entry}


def _slip(price, side, cfg, entry):
    ticks = float(cfg.get("slippage_ticks", 1)) * float(cfg.get("tick_size", 0.1))
    bps = float(cfg.get("slippage_bps", 0.5)) / 10_000.0
    slip = ticks + price * bps
    worse = (side == "LONG") if entry else (side == "SHORT")
    return price + slip if worse else price - slip


def _skip(skips, reason):
    skips[reason] = skips.get(reason, 0) + 1
