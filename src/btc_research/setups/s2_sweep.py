"""S2 liquidity sweep and reclaim. Structure only. Cost floor is pre-registered from the S1 stop-width result."""

from __future__ import annotations

from btc_research.features import atr
from btc_research.setups.s1_pullback import _last_closed_index, _simulate, _slip
from btc_research.structure import swing_points


def run_s2(bars_1m, bars_5m, bars_15m, cfg, sides):
    left, right = int(cfg["pivot_left"]), int(cfg["pivot_right"])
    highs, lows = swing_points([b.high for b in bars_15m], [b.low for b in bars_15m], left, right)
    atr_15 = atr([b.high for b in bars_15m], [b.low for b in bars_15m], [b.close for b in bars_15m], int(cfg["atr_period"]))
    min_stop = float(cfg.get("min_stop_bps", 25)) / 10_000.0
    skips, trades, next_free, i1 = {}, [], 0, 0
    for i15, bar in enumerate(bars_15m):
        now = bar.close_time
        if now < next_free:
            continue
        level = _swept_level(bar, highs, lows, i15)
        if level is None or level[0] not in sides:
            _skip(skips, "NO_SWEEP")
            continue
        side, pool, extreme = level
        if not _reclaimed(side, bars_5m, now, pool):
            _skip(skips, "NO_5M_RECLAIM")
            continue
        atr_m = atr_15[i15]
        if not atr_m:
            _skip(skips, "ATR_NOT_READY")
            continue
        stop = extreme - float(cfg["atr_buffer"]) * atr_m if side == "LONG" else extreme + float(cfg["atr_buffer"]) * atr_m
        while i1 < len(bars_1m) and bars_1m[i1].open_time < now:
            i1 += 1
        if i1 >= len(bars_1m):
            _skip(skips, "NO_ENTRY_BAR")
            continue
        entry_bar = bars_1m[i1]
        fill = _slip(entry_bar.open, side, cfg, True)
        risk = (fill - stop) if side == "LONG" else (stop - fill)
        if risk <= 0:
            _skip(skips, "INVALID_STOP")
            continue
        if risk / fill < min_stop:
            _skip(skips, "STOP_TOO_TIGHT")
            continue
        moved = (entry_bar.open - bar.close) if side == "LONG" else (bar.close - entry_bar.open)
        if moved > float(cfg["too_late_r"]) * risk:
            _skip(skips, "TOO_LATE")
            continue
        target = fill + float(cfg["target_r"]) * risk if side == "LONG" else fill - float(cfg["target_r"]) * risk
        trade = _simulate(bars_1m, i1, side, fill, stop, target, cfg)
        trade.update({"family": "S2", "side": side, "decision_time": now, "entry_time": entry_bar.open_time, "invalidation": extreme, "reason": "S2_SWEEP_RECLAIM"})
        trades.append(trade)
        next_free = trade["exit_time"]
    return trades, skips


def _swept_level(bar, highs, lows, i15):
    prior_lows = [p for p in lows if p.confirm_index < i15]
    prior_highs = [p for p in highs if p.confirm_index < i15]
    if prior_lows and bar.low < prior_lows[-1].price < bar.close:
        return "LONG", prior_lows[-1].price, bar.low
    if prior_highs and bar.high > prior_highs[-1].price > bar.close:
        return "SHORT", prior_highs[-1].price, bar.high
    return None


def _reclaimed(side, bars_5m, now, pool):
    idx = _last_closed_index(bars_5m, now)
    if idx < 0:
        return False
    return bars_5m[idx].close > pool if side == "LONG" else bars_5m[idx].close < pool


def _skip(skips, key):
    skips[key] = skips.get(key, 0) + 1
