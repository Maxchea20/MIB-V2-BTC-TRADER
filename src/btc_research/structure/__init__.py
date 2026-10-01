"""Confirmed swings. A pivot is invisible until right bars have closed."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pivot:
    index: int
    price: float
    confirm_index: int
    kind: str


def swing_points(highs, lows, left: int, right: int):
    highs_out = []
    lows_out = []
    n = len(highs)
    for i in range(left, n - right):
        window_h = highs[i - left : i + right + 1]
        window_l = lows[i - left : i + right + 1]
        if highs[i] == max(window_h) and highs[i] > max(highs[i - left : i] + highs[i + 1 : i + right + 1]):
            highs_out.append(Pivot(i, highs[i], i + right, "high"))
        if lows[i] == min(window_l) and lows[i] < min(lows[i - left : i] + lows[i + 1 : i + right + 1]):
            lows_out.append(Pivot(i, lows[i], i + right, "low"))
    return highs_out, lows_out


def visible(pivots, confirm_index: int):
    return [p for p in pivots if p.confirm_index <= confirm_index]
