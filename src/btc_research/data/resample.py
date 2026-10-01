"""Aggregate closed higher-timeframe bars from 1m. A bar exists only after it closes."""

from __future__ import annotations

from btc_research.data.loader import Bar

MS = {"5m": 300_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


def resample(bars, timeframe: str):
    step = MS[timeframe]
    if not bars:
        return []
    out = []
    bucket = None
    current = None
    for bar in bars:
        key = bar.open_time // step
        if bucket is None or key != bucket:
            if current is not None and current.close_time - current.open_time == step:
                out.append(current)
            bucket = key
            start = key * step
            current = Bar(start, start + step, bar.open, bar.high, bar.low, bar.close, bar.volume)
        else:
            current.high = max(current.high, bar.high)
            current.low = min(current.low, bar.low)
            current.close = bar.close
            current.volume += bar.volume
    if current is not None and current.close_time - current.open_time == step:
        out.append(current)
    return out
