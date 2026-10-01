"""Hunt C-FI replay. Fill is the next 1m open, and only if that open is still through the level."""

from __future__ import annotations

MS_5 = 300_000
MS_15 = 900_000


def run_hunt(bars_1m, bars_5m, bars_15m, bars_4h, cfg, sides):
    pivot_fast = int(cfg.get("pivot_fast", 5))
    pivot_internal = int(cfg.get("pivot_internal", 2))
    period = int(cfg.get("atr_period", 14))
    sl_atr = float(cfg.get("sl_atr", 1.5))
    tp_atr = float(cfg.get("tp_atr", 2.5))
    min_break = float(cfg.get("min_break_atr", 0.15))
    weather_on = bool(cfg.get("weather", True))
    retrace_atr = float(cfg.get("weather_retrace_atr", 1.0))
    quiet_ms = int(cfg.get("quiet_minutes", 15)) * 60_000
    extended_at = int(cfg.get("extended_bos", 3))

    atr_15 = _atr(bars_15m, period)
    fast = _events(bars_15m, pivot_fast, extended_at)
    internal = _events(bars_15m, pivot_internal, extended_at)
    weather = _weather(bars_4h, period, retrace_atr)

    skips, trades = {}, []
    next_free = 0
    spent = set()
    i1 = 0

    for bar in bars_5m:
        now = bar.close_time
        if now < next_free:
            continue
        parent = bar.open_time - (bar.open_time % MS_15)
        slot = (bar.open_time % MS_15) // MS_5 + 1
        if slot not in (1, 2, 3) or (parent, slot) in spent:
            continue

        closed = [b for b in bars_15m if b.close_time <= parent]
        if len(closed) < 60:
            _skip(skips, "WARMUP")
            continue
        thesis = _thesis(fast, internal, closed)
        if thesis is None:
            _skip(skips, "NO_THESIS")
            continue
        side = thesis["side"]
        if side not in sides:
            _skip(skips, "SIDE_FILTER")
            continue
        flag = _latest_weather(weather, now)
        if weather_on and not _side_ok(flag, side):
            _skip(skips, "WEATHER")
            continue
        atr_v = _latest_atr(bars_15m, atr_15, parent)
        if not atr_v:
            _skip(skips, "ATR_NOT_READY")
            continue

        fill_level, path = _answer(slot, side, bar, thesis, closed[-1], atr_v, min_break)
        if fill_level is None:
            _skip(skips, "NO_ANSWER")
            continue

        while i1 < len(bars_1m) and bars_1m[i1].open_time < now:
            i1 += 1
        if i1 >= len(bars_1m):
            _skip(skips, "NO_ENTRY_BAR")
            continue
        open_px = bars_1m[i1].open
        if side == "LONG" and open_px < fill_level:
            _skip(skips, "OPEN_NOT_THROUGH")
            continue
        if side == "SHORT" and open_px > fill_level:
            _skip(skips, "OPEN_NOT_THROUGH")
            continue

        entry = _slip(open_px, side, cfg, True)
        stop = entry - sl_atr * atr_v if side == "LONG" else entry + sl_atr * atr_v
        target = entry + tp_atr * atr_v if side == "LONG" else entry - tp_atr * atr_v
        risk = abs(entry - stop)
        if risk <= 0:
            _skip(skips, "INVALID_STOP")
            continue

        trade = _simulate(bars_1m, i1, side, entry, stop, target, risk, cfg)
        trade.update({"family": "HUNT", "side": side, "decision_time": now, "entry_time": bars_1m[i1].open_time, "reason": path, "gate": thesis["gate"], "event": thesis["event"], "slot": slot, "thesis_level": thesis["level"], "invalidation": thesis["invalid"], "atr_15m": atr_v, "weather": flag})
        trades.append(trade)
        spent.add((parent, slot))
        next_free = trade["exit_time"] + quiet_ms

    return trades, skips


def _thesis(fast, internal, closed):
    last_close = closed[-1].close_time
    known_fast = [e for e in fast if e["ts"] <= last_close]
    known_internal = [e for e in internal if e["ts"] <= last_close]
    fresh_fast = _fresh(known_fast, last_close)
    if fresh_fast is not None:
        return fresh_fast
    fresh_in = _fresh(known_internal, last_close)
    if fresh_in is not None:
        return fresh_in
    armed = _rearm(known_fast, closed) or _rearm(known_internal, closed)
    if armed is None:
        return None
    armed = dict(armed)
    armed["gate"] = "rearm"
    return armed


def _fresh(events, last_close):
    if not events or events[-1]["ts"] != last_close or events[-1]["extended"]:
        return None
    return events[-1]


def _rearm(events, closed):
    if not events:
        return None
    last = events[-1]
    if last["extended"]:
        return None
    for bar in closed:
        if bar.close_time <= last["ts"]:
            continue
        if last["side"] == "LONG" and bar.close < last["invalid"]:
            return None
        if last["side"] == "SHORT" and bar.close > last["invalid"]:
            return None
    return last


def _answer(slot, side, bar, thesis, prior, atr_v, min_break):
    level = thesis["level"]
    if slot in (1, 2):
        tapped = bar.high >= level if side == "LONG" else bar.low <= level
        if tapped:
            return level, f"v2_tap_slot{slot}"
        return None, None
    broke = bar.close > prior.high and (bar.close - prior.high) >= min_break * atr_v
    broke_dn = bar.close < prior.low and (prior.low - bar.close) >= min_break * atr_v
    if side == "LONG" and broke:
        return prior.high, "impulse_3"
    if side == "SHORT" and broke_dn:
        return prior.low, "impulse_3"
    return None, None


def _events(bars, pivot, extended_at):
    highs, lows = _swings(bars, pivot)
    out = []
    last_high = last_low = None
    bias = None
    streak = 0
    for i, bar in enumerate(bars):
        if highs[i] is not None:
            last_high = highs[i]
        if lows[i] is not None:
            last_low = lows[i]
        if last_high is None or last_low is None or i < pivot:
            continue
        side = event = None
        if bar.close > last_high:
            side, event = "LONG", ("BOS" if bias == "LONG" else "CHoCH")
            level, invalid = last_high, last_low
        elif bar.close < last_low:
            side, event = "SHORT", ("BOS" if bias == "SHORT" else "CHoCH")
            level, invalid = last_low, last_high
        if side is None:
            continue
        if event == "CHoCH" or side != bias:
            streak = 0
        else:
            streak += 1
        bias = side
        out.append({"ts": bar.close_time, "side": side, "event": event, "level": level, "invalid": invalid, "extended": event == "BOS" and streak >= extended_at, "gate": "cfast" if pivot >= 5 else "internal"})
    return out


def _swings(bars, pivot):
    n = len(bars)
    highs = [None] * n
    lows = [None] * n
    for i in range(pivot, n - pivot):
        h, lo = bars[i].high, bars[i].low
        if all(h > bars[i - k].high and h >= bars[i + k].high for k in range(1, pivot + 1)):
            highs[i + pivot] = h
        if all(lo < bars[i - k].low and lo <= bars[i + k].low for k in range(1, pivot + 1)):
            lows[i + pivot] = lo
    return highs, lows


def _weather(bars, period, retrace_atr):
    if len(bars) < period + 5:
        return []
    atr_v = _atr(bars, period)
    highs, lows = _swings(bars, 2)
    out = []
    extreme_high = extreme_low = None
    bias = None
    for i, bar in enumerate(bars):
        if highs[i] is not None:
            extreme_high = highs[i]
            bias = "UP"
        if lows[i] is not None:
            extreme_low = lows[i]
            bias = "DOWN"
        a = atr_v[i]
        flag = "CHOP"
        if a and bias == "UP" and extreme_high is not None:
            flag = "CHOP" if (extreme_high - bar.close) >= retrace_atr * a else "SWING_UP"
        elif a and bias == "DOWN" and extreme_low is not None:
            flag = "CHOP" if (bar.close - extreme_low) >= retrace_atr * a else "SWING_DOWN"
        out.append((bar.close_time, flag))
    return out


def _latest_weather(rows, now):
    flag = "CHOP"
    for ts, value in rows:
        if ts > now:
            break
        flag = value
    return flag


def _side_ok(flag, side):
    if flag == "SWING_UP":
        return side == "LONG"
    if flag == "SWING_DOWN":
        return side == "SHORT"
    return True


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
