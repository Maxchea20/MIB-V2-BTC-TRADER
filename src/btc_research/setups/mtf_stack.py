"""4h trend, 1h break, 15m entry. Fill is a 1m touch of the 15m level."""

from __future__ import annotations

import bisect

from btc_research.setups.hunt_lookback import _atr, _latest_atr, _simulate, _slip, _touch


def run_mtf(bars_1m, bars_15m, bars_1h, bars_4h, cfg, sides):
    lookback_4h = int(cfg.get("lookback_4h", 20))
    lookback_1h = int(cfg.get("lookback_1h", 20))
    lookback_15 = int(cfg.get("lookback_15", 20))
    sl_atr = float(cfg.get("sl_atr", 1.5))
    tp_atr = float(cfg.get("tp_atr", 2.5))
    quiet_ms = int(cfg.get("quiet_minutes", 15)) * 60_000
    period = int(cfg.get("atr_period", 14))
    # fill_mode "legacy": the 15m bar must CLOSE beyond the level, then the fill is booked at the first 1m touch inside that bar (a price in the past: not tradable).
    # fill_mode "next_open": same signal, but the fill is the first 1m open after the 15m bar closes (what you can really get).
    # fill_mode "touch": no wait for the 15m close; a resting stop order at the level fills on the first touch in the bar (every touch counts, including ones that reverse).
    fill_mode = cfg.get("fill_mode", "legacy")
    # h4_gate "trend" (default): the 4h close vs 20 bars earlier sets the only allowed side. "any": no 4h filter, both sides allowed.
    # h1_gate "break" (default): the 1h must have closed beyond its prior 20-bar high/low in that side. "any": no 1h filter.
    # With both set to "any" the side is just the 15m break: long above the prior 20-bar high, short below the prior 20-bar low.
    h4_gate = cfg.get("h4_gate", "trend")
    h1_gate = cfg.get("h1_gate", "break")
    atr_tf = cfg.get("atr_tf", "15m")
    atr_bars = {"15m": bars_15m, "1h": bars_1h, "4h": bars_4h}[atr_tf]
    atr_15 = _atr(atr_bars, period)
    times_1m = [b.open_time for b in bars_1m] if fill_mode == "next_open" else None
    skips, trades = {}, []
    next_free = 0
    for i, bar in enumerate(bars_15m):
        now = bar.close_time
        dec = bar.open_time if fill_mode == "touch" else now
        if dec < next_free:
            continue
        if i < lookback_15:
            _skip(skips, "WARMUP")
            continue
        trend4 = _trend(bars_4h, dec, lookback_4h)
        if h4_gate == "trend":
            if trend4 == "NONE":
                _skip(skips, "NO_4H_TREND")
                continue
            if trend4 not in sides:
                _skip(skips, "SIDE_FILTER")
                continue
            options = [trend4]
        else:
            options = [x for x in ("LONG", "SHORT") if x in sides]
        window = bars_15m[i - lookback_15:i]
        found, saw_1h = [], False
        for side in options:
            if h1_gate == "break" and not _broke(bars_1h, dec, lookback_1h, side):
                continue
            saw_1h = True
            level = max(b.high for b in window) if side == "LONG" else min(b.low for b in window)
            if fill_mode != "touch" and not (bar.close > level if side == "LONG" else bar.close < level):
                continue
            if fill_mode == "next_open":
                i_fill = bisect.bisect_left(times_1m, now)
                hit = (i_fill, bars_1m[i_fill].open) if i_fill < len(bars_1m) else None
            elif fill_mode == "touch":
                hit = _stop_touch(bars_1m, bar.open_time, now, side, level)
            else:
                hit = _touch(bars_1m, bar.open_time, now, side, level)
            if hit is None:
                _skip(skips, "NO_LIMIT_TOUCH")
                continue
            found.append((hit[0], side, level, hit))
        if not found:
            if not saw_1h:
                _skip(skips, "NO_1H_BREAK")
            else:
                _skip(skips, "NO_15M_BREAK")
            continue
        _, trend, level, hit = min(found, key=lambda x: x[0])
        i_fill, raw = hit
        atr_v = _latest_atr(atr_bars, atr_15, dec)
        if not atr_v:
            _skip(skips, "ATR_NOT_READY")
            continue
        entry = _slip(raw, trend, cfg, True)
        risk = sl_atr * atr_v
        if risk <= 0:
            _skip(skips, "INVALID_STOP")
            continue
        stop = entry - risk if trend == "LONG" else entry + risk
        target = entry + tp_atr * atr_v if trend == "LONG" else entry - tp_atr * atr_v
        trade = _simulate(bars_1m, i_fill, trend, entry, stop, target, risk, cfg)
        trade.update({"family": "MTF", "side": trend, "decision_time": now, "entry_time": bars_1m[i_fill].open_time, "reason": "15m_break", "gate": "fresh", "event": "BOS", "slot": 1, "thesis_level": level, "invalidation": level, "atr_15m": atr_v, "weather": trend})
        trades.append(trade)
        next_free = trade["exit_time"] + quiet_ms
    return trades, skips


def _stop_touch(bars, start, end, side, level):
    """A resting STOP order at the level: fills only when price trades up to it (long) or down to it (short). A bar that opens beyond it fills at the open."""
    for i in range(_first(bars, start), len(bars)):
        bar = bars[i]
        if bar.open_time >= end:
            return None
        if side == "LONG" and bar.high >= level:
            return i, max(level, bar.open)
        if side == "SHORT" and bar.low <= level:
            return i, min(level, bar.open)
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


def _trend(bars, now, lookback):
    closed = [b for b in bars if b.close_time <= now]
    if len(closed) <= lookback:
        return "NONE"
    if closed[-1].close > closed[-1 - lookback].close:
        return "LONG"
    if closed[-1].close < closed[-1 - lookback].close:
        return "SHORT"
    return "NONE"


def _broke(bars, now, lookback, side):
    closed = [b for b in bars if b.close_time <= now]
    if len(closed) <= lookback:
        return False
    window = closed[-1 - lookback:-1]
    bar = closed[-1]
    if side == "LONG":
        return bar.close > max(b.high for b in window)
    return bar.close < min(b.low for b in window)


def _skip(skips, reason):
    skips[reason] = skips.get(reason, 0) + 1
