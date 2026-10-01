"""20-bar 15m sign, 50-bar 5m break, pullback tap, no rearm.

Fill is the first 1m bar inside the signal 5m bar that trades through the level.
"""

from __future__ import annotations


def run_hunt20(bars_1m, bars_5m, bars_15m, cfg, sides):
    lookback_15 = int(cfg.get("lookback_15", 20))
    lookback_5 = int(cfg.get("lookback_5", 50))
    period = int(cfg.get("atr_period", 14))
    sl_atr = float(cfg.get("sl_atr", 1.5))
    tp_atr = float(cfg.get("tp_atr", 2.5))
    quiet_ms = int(cfg.get("quiet_minutes", 15)) * 60_000
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
        stop = entry - sl_atr * atr_v if side == "LONG" else entry + sl_atr * atr_v
        target = entry + tp_atr * atr_v if side == "LONG" else entry - tp_atr * atr_v
        risk = abs(entry - stop)
        if risk <= 0:
            _skip(skips, "INVALID_STOP")
            continue
        trade = _simulate(bars_1m, i_fill, side, entry, stop, target, risk, cfg)
        trade.update({"family": "HUNT20", "side": side, "decision_time": now, "entry_time": bars_1m[i_fill].open_time, "reason": "pullback_tap", "gate": "fresh", "event": event, "slot": ((bar.open_time % 900_000) // 300_000) + 1, "thesis_level": level, "invalidation": prior_low if side == "LONG" else prior_high, "atr_15m": atr_v, "weather": "NONE"})
        trades.append(trade)
        next_free = trade["exit_time"] + quiet_ms
    return trades, skips


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
