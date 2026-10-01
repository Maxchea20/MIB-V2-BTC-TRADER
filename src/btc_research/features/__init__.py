"""Causal ATR. Value at index i uses bars up to and including i."""

from __future__ import annotations


def atr(highs, lows, closes, period):
    n = len(closes)
    out = [None] * n
    if n == 0:
        return out
    trs = [highs[0] - lows[0]]
    for i in range(1, n):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    if n < period:
        return out
    prev = sum(trs[:period]) / period
    out[period - 1] = prev
    for i in range(period, n):
        prev = (prev * (period - 1) + trs[i]) / period
        out[i] = prev
    return out
