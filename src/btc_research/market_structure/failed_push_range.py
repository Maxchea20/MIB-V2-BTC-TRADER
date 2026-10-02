"""Failed-push range. A return inside expands the box to the failed extreme."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PushParams:
    pivot_left: int = 2
    pivot_right: int = 2
    similar_atr: float = 0.25
    body_min: float = 0.50


@dataclass(frozen=True)
class PushRange:
    active: bool
    high: float | None
    low: float | None
    a: float | None
    a1: float | None
    aa: float | None
    a2: float | None
    ab: float | None
    phase: str


def detect_push_range(bars, params: PushParams | None = None) -> PushRange:
    params = params or PushParams()
    empty = PushRange(False, None, None, None, None, None, None, None, "NONE")
    if len(bars) < params.pivot_left + params.pivot_right + 8:
        return empty
    atr = _atr(bars)
    if not atr:
        return empty
    pivots = _pivots(bars, params.pivot_left, params.pivot_right)
    state = _sequence(pivots, atr * params.similar_atr)
    if not state:
        return empty
    high, low, phase = _walk(bars, state["high"], state["low"], params.body_min)
    return PushRange(phase != "BREAKOUT_CONFIRMED", high, low, state["a"], state["a1"], state["aa"], state["a2"], state["ab"], phase)


def _sequence(pivots, similar):
    found = None
    for i, (kind, price) in enumerate(pivots):
        if kind != "high":
            continue
        a1 = _next(pivots, i, "low")
        if not a1 or a1[1] >= price:
            continue
        aa = _next(pivots, a1[0], "high")
        if not aa or aa[1] >= price or aa[1] <= a1[1]:
            continue
        a2 = _next(pivots, aa[0], "low")
        if not a2 or a2[1] < a1[1] - similar:
            continue
        ab = _next(pivots, a2[0], "high")
        if not ab or ab[1] > aa[1] + similar or ab[1] <= a2[1]:
            continue
        found = {"a": price, "a1": a1[1], "aa": aa[1], "a2": a2[1], "ab": ab[1], "high": aa[1], "low": a1[1]}
    return found


def _next(pivots, start, kind):
    for j in range(start + 1, len(pivots)):
        if pivots[j][0] == kind:
            return j, pivots[j][1]
    return None


def _walk(bars, high, low, body_min):
    phase = "RANGE"
    side = None
    extreme = None
    for bar in bars:
        close = _close(bar)
        if phase == "BREAKOUT_CANDIDATE":
            extreme = max(extreme, _high(bar)) if side == "up" else min(extreme, _low(bar))
            if low <= close <= high:
                if side == "up":
                    high = extreme
                else:
                    low = extreme
                phase = "RANGE"
                side = None
                extreme = None
                continue
            if _solid(bar, high, low, body_min):
                phase = "BREAKOUT_CONFIRMED"
            continue
        if _solid(bar, high, low, body_min):
            phase = "BREAKOUT_CANDIDATE"
            side = "up" if close > high else "down"
            extreme = _high(bar) if side == "up" else _low(bar)
    return high, low, phase


def _solid(bar, high, low, body_min):
    span = _high(bar) - _low(bar)
    body = abs(_close(bar) - _open(bar))
    if span <= 0 or body / span < body_min:
        return False
    if _close(bar) > high and _close(bar) > _open(bar):
        return True
    if _close(bar) < low and _close(bar) < _open(bar):
        return True
    return False


def _pivots(bars, left, right):
    raw = []
    for i in range(left, len(bars) - right):
        hs = [_high(b) for b in bars[i - left : i + right + 1]]
        ls = [_low(b) for b in bars[i - left : i + right + 1]]
        if _high(bars[i]) >= max(hs) and _high(bars[i]) >= max(_high(b) for b in bars[i + 1 : i + right + 1]):
            raw.append(("high", _high(bars[i])))
        elif _low(bars[i]) <= min(ls) and _low(bars[i]) <= min(_low(b) for b in bars[i + 1 : i + right + 1]):
            raw.append(("low", _low(bars[i])))
    out = []
    for kind, price in raw:
        if out and out[-1][0] == kind:
            out[-1] = (kind, max(price, out[-1][1]) if kind == "high" else min(price, out[-1][1]))
        else:
            out.append((kind, price))
    return out


def _atr(bars):
    if len(bars) < 15:
        return None
    acc = 0.0
    prev = _close(bars[-15])
    for bar in bars[-14:]:
        acc += max(_high(bar) - _low(bar), abs(_high(bar) - prev), abs(_low(bar) - prev))
        prev = _close(bar)
    value = acc / 14
    return value or None


def _high(bar):
    return bar["high"] if isinstance(bar, dict) else bar.high


def _low(bar):
    return bar["low"] if isinstance(bar, dict) else bar.low


def _open(bar):
    return bar["open"] if isinstance(bar, dict) else bar.open


def _close(bar):
    return bar["close"] if isinstance(bar, dict) else bar.close
