"""4h trend, 1h break, 15m entry. Fill is a 1m touch of the 15m level."""

from __future__ import annotations

from btc_research.setups.hunt_lookback import _atr, _latest_atr, _simulate, _slip, _touch


def run_mtf(bars_1m, bars_15m, bars_1h, bars_4h, cfg, sides):
    lookback_4h = int(cfg.get("lookback_4h", 20))
    lookback_1h = int(cfg.get("lookback_1h", 20))
    lookback_15 = int(cfg.get("lookback_15", 20))
    sl_atr = float(cfg.get("sl_atr", 1.5))
    tp_atr = float(cfg.get("tp_atr", 2.5))
    quiet_ms = int(cfg.get("quiet_minutes", 15)) * 60_000
    atr_15 = _atr(bars_15m, int(cfg.get("atr_period", 14)))
    skips, trades = {}, []
    next_free = 0
    for i, bar in enumerate(bars_15m):
        now = bar.close_time
        if now < next_free:
            continue
        if i < lookback_15:
            _skip(skips, "WARMUP")
            continue
        trend = _trend(bars_4h, now, lookback_4h)
        if trend == "NONE":
            _skip(skips, "NO_4H_TREND")
            continue
        if trend not in sides:
            _skip(skips, "SIDE_FILTER")
            continue
        if not _broke(bars_1h, now, lookback_1h, trend):
            _skip(skips, "NO_1H_BREAK")
            continue
        window = bars_15m[i - lookback_15:i]
        level = max(b.high for b in window) if trend == "LONG" else min(b.low for b in window)
        broke = bar.close > level if trend == "LONG" else bar.close < level
        if not broke:
            _skip(skips, "NO_15M_BREAK")
            continue
        hit = _touch(bars_1m, bar.open_time, now, trend, level)
        if hit is None:
            _skip(skips, "NO_LIMIT_TOUCH")
            continue
        i_fill, raw = hit
        atr_v = _latest_atr(bars_15m, atr_15, now)
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
