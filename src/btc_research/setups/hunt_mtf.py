"""4h trend, 1h confirmation, 15m break entry."""

from __future__ import annotations

from btc_research.setups.hunt_lookback import run_hunt20


def run_hunt_mtf(bars_1m, bars_5m, bars_15m, bars_1h, bars_4h, cfg, sides):
    cfg = dict(cfg)
    cfg["_bars_1h"] = bars_1h
    cfg["_bars_4h"] = bars_4h
    cfg["mtf_filter"] = True
    return run_hunt20(bars_1m, bars_5m, bars_15m, cfg, sides)
