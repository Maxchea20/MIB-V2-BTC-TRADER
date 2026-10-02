"""Structural range detector. It does not fire trades and it does not change Hunt."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RangeParams:
    lookback: int = 80
    pivot_left: int = 2
    pivot_right: int = 2
    tolerance_atr: float = 0.30
    containment_min: float = 0.75
    efficiency_max: float = 0.30
    slope_max: float = 0.10
    min_touches: int = 2
    score_min: float = 70.0


@dataclass(frozen=True)
class RangeState:
    active: bool
    high: float | None
    low: float | None
    started_at: int | None
    duration_bars: int
    score: float
    containment: float
    efficiency: float
    slope: float
    upper_touches: int
    lower_touches: int
    failed_breaks: int
    context: str
    phase: str


def detect_range(bars_15m, bars_1h=None, params: RangeParams | None = None) -> RangeState:
    params = params or RangeParams()
    context = _context(bars_1h, params) if bars_1h else "UNKNOWN"
    window = list(bars_15m)[-params.lookback :]
    if len(window) < params.pivot_left + params.pivot_right + 16:
        return _empty(context)
    atr = _atr(window)
    if not atr:
        return _empty(context)
    highs, lows = _pivots(window, params.pivot_left, params.pivot_right)
    upper = _cluster([price for _, price in highs], atr * params.tolerance_atr, high=True)
    lower = _cluster([price for _, price in lows], atr * params.tolerance_atr, high=False)
    if upper is None or lower is None or upper <= lower:
        return _empty(context)
    closes = [_close(b) for b in window]
    inside = sum(lower <= c <= upper for c in closes) / len(closes)
    efficiency = _efficiency(closes)
    slope = abs(_slope(closes) / atr)
    band = atr * params.tolerance_atr
    upper_touches = sum(abs(_high(b) - upper) <= band for b in window)
    lower_touches = sum(abs(_low(b) - lower) <= band for b in window)
    failed = _failed(window, upper, lower, band)
    score = 0.0
    score += 25 if inside >= params.containment_min else 0
    score += 20 if efficiency <= params.efficiency_max else 0
    score += 15 if slope <= params.slope_max else 0
    score += 15 if upper_touches >= params.min_touches else 0
    score += 15 if lower_touches >= params.min_touches else 0
    score += 10 if failed else 0
    first = next((i for i, b in enumerate(window) if abs(_high(b) - upper) <= band or abs(_low(b) - lower) <= band), 0)
    active = score >= params.score_min and upper_touches >= params.min_touches and lower_touches >= params.min_touches
    return RangeState(
        active=active,
        high=upper,
        low=lower,
        started_at=_time(window[first]),
        duration_bars=len(window) - first,
        score=score,
        containment=round(inside, 4),
        efficiency=round(efficiency, 4),
        slope=round(slope, 4),
        upper_touches=upper_touches,
        lower_touches=lower_touches,
        failed_breaks=failed,
        context=context,
        phase="RANGE" if active else "NONE",
    )


def react(state: RangeState, closed_bar, previous: str = "RANGE") -> str:
    """A first close outside is a candidate. The next close decides."""
    if not state.active or state.high is None or state.low is None:
        return "NONE"
    close = _close(closed_bar)
    outside = close > state.high or close < state.low
    if previous == "BREAKOUT_CANDIDATE":
        return "BREAKOUT_CONFIRMED" if outside else "RANGE_REJECTION"
    if outside:
        return "BREAKOUT_CANDIDATE"
    return "RANGE"


def _context(bars, params: RangeParams) -> str:
    return "RANGE" if detect_range(bars, None, params).active else "TREND"


def _empty(context: str) -> RangeState:
    return RangeState(False, None, None, None, 0, 0, 0, 0, 0, 0, 0, 0, context, "NONE")


def _pivots(bars, left: int, right: int):
    highs, lows = [], []
    for i in range(left, len(bars) - right):
        hs = [_high(b) for b in bars[i - left : i + right + 1]]
        ls = [_low(b) for b in bars[i - left : i + right + 1]]
        right_high = max(_high(b) for b in bars[i + 1 : i + right + 1])
        right_low = min(_low(b) for b in bars[i + 1 : i + right + 1])
        if _high(bars[i]) >= max(hs) and _high(bars[i]) >= right_high:
            highs.append((i + right, _high(bars[i])))
        if _low(bars[i]) <= min(ls) and _low(bars[i]) <= right_low:
            lows.append((i + right, _low(bars[i])))
    return highs, lows


def _cluster(prices, tolerance, high: bool):
    if not prices:
        return None
    groups = []
    for price in sorted(prices):
        if groups and abs(price - sum(groups[-1]) / len(groups[-1])) <= tolerance:
            groups[-1].append(price)
        else:
            groups.append([price])
    chosen = max(groups, key=len)
    if len(chosen) < 2:
        return None
    return max(chosen) if high else min(chosen)


def _failed(bars, high, low, tolerance) -> int:
    count = 0
    for bar in bars:
        if _high(bar) > high + tolerance and _close(bar) < high:
            count += 1
        if _low(bar) < low - tolerance and _close(bar) > low:
            count += 1
    return count


def _efficiency(closes) -> float:
    travel = sum(abs(b - a) for a, b in zip(closes, closes[1:]))
    if travel <= 0:
        return 1.0
    return abs(closes[-1] - closes[0]) / travel


def _slope(closes) -> float:
    n = len(closes)
    mean_x = (n - 1) / 2
    mean_y = sum(closes) / n
    den = sum((i - mean_x) ** 2 for i in range(n))
    if den == 0:
        return 0.0
    return sum((i - mean_x) * (y - mean_y) for i, y in enumerate(closes)) / den


def _atr(bars) -> float | None:
    if len(bars) < 15:
        return None
    acc = 0.0
    prev = _close(bars[-15])
    for bar in bars[-14:]:
        acc += max(_high(bar) - _low(bar), abs(_high(bar) - prev), abs(_low(bar) - prev))
        prev = _close(bar)
    return acc / 14


def _high(bar):
    return bar["high"] if isinstance(bar, dict) else bar.high


def _low(bar):
    return bar["low"] if isinstance(bar, dict) else bar.low


def _close(bar):
    return bar["close"] if isinstance(bar, dict) else bar.close


def _time(bar):
    if isinstance(bar, dict):
        return bar.get("open_time")
    return getattr(bar, "open_time", None)
