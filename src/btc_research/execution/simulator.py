"""Could this order really have been filled, and at what price? Pure functions over 1m bars. No strategy logic lives here.

Lifecycle:  SIGNAL (closed candle) -> order submitted at signal_time + latency -> EXECUTABLE? -> FILLED / MISSED_FILL -> protective orders
active from fill_time + latency -> each later 1m bar is resolved here -> exit fill.

Rules (all documented, all configurable in ExecutionConfig):
* A bar is "after" an order only if bar.open_time >= the order's submit time. A bar that opened before submission may contain prices that
  happened before the order existed, so it can never fill the order.
* Market order: fills at the open of the first bar that opens at or after the submit time (1m data cannot resolve prices inside a minute, so any
  latency that crosses a minute boundary moves the fill to the next minute's open), plus slippage against you. Optional price protection
  (max_entry_slippage_bps) turns it into an IOC-style order: if the price has run further than the cap, the order is MISSED_FILL.
* Limit order: rests from the submit time. Buy fills when a later bar trades THROUGH the price by limit_trade_through_ticks (queue position is
  unknown, so touching is not enough). A limit that is already marketable at the first bar fills at the open as a taker, capped at the limit price.
* Resting stop-market: triggers when a bar trades through the stop. If the bar OPENS beyond the stop (gap) the fill is the open, otherwise the
  stop price, and slippage is always added against you. Exit time inside a bar is unknown, so it is booked at the end of that bar.
* Resting take-profit (limit): needs a trade-through of limit_trade_through_ticks, fills at the limit price (a resting order never gets better).
* Stop and target both touched inside the same 1m bar: OHLC cannot say which came first. intrabar_policy = conservative (stop), optimistic
  (target) or unresolved (the trade is flagged and excluded from the PnL, never silently resolved).

Values below are ASSUMPTIONS carried over from the earlier engines (1 tick + 0.5 bp slippage, 2 bp taker fee) or documented guesses (latency, trade-through).
They are not calibrated to MEXC. Replace them from the live order/fill logs when those are available.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class ExecutionConfig:
    execution_latency_seconds: float = 1.0   # candle-close detection + order round trip. A guess; any value > 0 moves a market fill to the next 1m open.
    entry_slippage_bps: float = 0.5          # same as every earlier engine
    exit_slippage_bps: float = 0.5
    slippage_ticks: float = 1.0
    tick_size: float = 0.1                   # Binance USD-M BTCUSDT default. NOT read from MEXC.
    fee_bps_per_side: float = 2.0            # 0.02% taker, as in every earlier run. Applied to entry and exit notional.
    limit_trade_through_ticks: float = 1.0   # queue-position proxy for resting limits
    max_entry_slippage_bps: float | None = None   # None = plain market order. A number = IOC-style price protection.
    intrabar_policy: str = "conservative"    # conservative | optimistic | unresolved
    leverage: float | None = None            # isolated margin. None = not modelled.
    maintenance_margin_rate: float | None = None  # needed for a liquidation check. None = not modelled. Not calibrated.

    @property
    def latency_ms(self) -> int:
        return int(round(self.execution_latency_seconds * 1000))

    def with_(self, **kw) -> "ExecutionConfig":
        return replace(self, **kw)


@dataclass
class Fill:
    status: str                  # FILLED | MISSED_FILL
    reason: str                  # why a fill was missed, or the execution kind
    order_type: str              # MARKET | LIMIT | STOP_MARKET
    side: str                    # position side: LONG | SHORT
    purpose: str                 # ENTRY | EXIT
    submit_time: int
    intended_price: float | None
    fill_time: int | None = None
    raw_price: float | None = None     # executable price before slippage
    fill_price: float | None = None
    slippage: float = 0.0              # price units, adverse = positive
    liquidity: str = "taker"
    execution_model: str = ""


def slippage(price: float, cfg: ExecutionConfig, entering: bool) -> float:
    bps = cfg.entry_slippage_bps if entering else cfg.exit_slippage_bps
    return cfg.slippage_ticks * cfg.tick_size + price * bps / 10_000.0


def _sign(side: str) -> int:
    return 1 if side == "LONG" else -1


def _worse(side: str, entering: bool) -> int:
    """+1 if a worse price is a HIGHER price. Entering a long buys (higher is worse); exiting a long sells (lower is worse)."""
    return _sign(side) if entering else -_sign(side)


def market_fill(bars, times, side, submit_time, cfg, entering=True, intended=None, purpose=None):
    purpose = purpose or ("ENTRY" if entering else "EXIT")
    i = bisect.bisect_left(times, submit_time)
    if i >= len(bars):
        return Fill("MISSED_FILL", "NO_DATA", "MARKET", side, purpose, submit_time, intended, execution_model="market_next_1m_open")
    raw = bars[i].open
    slip = slippage(raw, cfg, entering)
    fill = raw + _worse(side, entering) * slip
    if entering and intended and cfg.max_entry_slippage_bps is not None:
        adverse_bps = _worse(side, True) * (fill - intended) / intended * 10_000.0
        if adverse_bps > cfg.max_entry_slippage_bps:
            return Fill("MISSED_FILL", "PRICE_MOVED_AWAY", "MARKET", side, purpose, submit_time, intended, fill_time=bars[i].open_time,
                        raw_price=raw, execution_model="market_ioc_price_protection")
    return Fill("FILLED", "MARKET", "MARKET", side, purpose, submit_time, intended, bars[i].open_time, raw, fill, slip, "taker", "market_next_1m_open")


def limit_fill(bars, times, side, price, submit_time, cfg, entering=True, ttl_ms=None, purpose=None):
    """Resting limit order. BUY when entering a long or exiting a short; SELL otherwise."""
    purpose = purpose or ("ENTRY" if entering else "EXIT")
    buy = _worse(side, entering) == 1
    through = cfg.limit_trade_through_ticks * cfg.tick_size
    start = bisect.bisect_left(times, submit_time)
    for i in range(start, len(bars)):
        bar = bars[i]
        if ttl_ms is not None and bar.open_time >= submit_time + ttl_ms:
            return Fill("MISSED_FILL", "EXPIRED", "LIMIT", side, purpose, submit_time, price, execution_model="limit_resting")
        marketable = bar.open <= price if buy else bar.open >= price
        if marketable:
            raw = bar.open
            slip = slippage(raw, cfg, entering)
            fill = min(price, raw + slip) if buy else max(price, raw - slip)
            return Fill("FILLED", "MARKETABLE_AT_FIRST_BAR", "LIMIT", side, purpose, submit_time, price, bar.open_time, raw, fill, abs(fill - raw), "taker", "limit_marketable")
        reached = bar.low <= price - through if buy else bar.high >= price + through
        if reached:
            return Fill("FILLED", "TRADED_THROUGH", "LIMIT", side, purpose, submit_time, price, bar.close_time, price, price, 0.0, "maker", "limit_resting")
    return Fill("MISSED_FILL", "NOT_REACHED", "LIMIT", side, purpose, submit_time, price, execution_model="limit_resting")


def resolve_bar(bar, side, stop, target, cfg):
    """One 1m bar against a resting stop-market and a resting take-profit limit of an open position.
    Returns None, or a dict: reason (STOP | TARGET | UNRESOLVED_BOTH_HIT), raw, fill, time, order_type, liquidity."""
    sign = _sign(side)
    through = cfg.limit_trade_through_ticks * cfg.tick_size
    stop_hit = stop is not None and ((bar.low <= stop) if sign == 1 else (bar.high >= stop))
    tgt_hit = target is not None and ((bar.high >= target + through) if sign == 1 else (bar.low <= target - through))
    if not stop_hit and not tgt_hit:
        return None
    stop_gap = stop_hit and ((bar.open <= stop) if sign == 1 else (bar.open >= stop))

    def stop_exit():
        raw = bar.open if stop_gap else stop
        fill = raw - sign * slippage(raw, cfg, False)
        return {"reason": "STOP", "raw": raw, "fill": fill, "time": bar.open_time if stop_gap else bar.close_time, "order_type": "STOP_MARKET", "liquidity": "taker"}

    def target_exit():
        return {"reason": "TARGET", "raw": target, "fill": target, "time": bar.close_time, "order_type": "LIMIT", "liquidity": "maker"}

    if stop_hit and tgt_hit:
        if stop_gap:
            return stop_exit()
        policy = cfg.intrabar_policy
        if policy == "optimistic":
            return target_exit()
        if policy == "unresolved":
            return {"reason": "UNRESOLVED_BOTH_HIT", "raw": None, "fill": None, "time": bar.close_time, "order_type": "UNRESOLVED", "liquidity": ""}
        return stop_exit()
    return stop_exit() if stop_hit else target_exit()


def liquidation_price(side, entry, cfg):
    """Isolated-margin liquidation price, only if leverage and a maintenance margin rate are configured. Otherwise None (not modelled)."""
    if cfg.leverage is None or cfg.maintenance_margin_rate is None:
        return None
    return entry * (1 - _sign(side) * (1.0 / cfg.leverage - cfg.maintenance_margin_rate))
