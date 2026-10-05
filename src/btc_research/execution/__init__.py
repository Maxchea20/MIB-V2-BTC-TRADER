"""Execution simulator: decides whether and at what price an order could really have executed, from 1m data. The strategy never decides fills."""

from btc_research.execution.simulator import (  # noqa: F401
    ExecutionConfig,
    Fill,
    limit_fill,
    liquidation_price,
    market_fill,
    resolve_bar,
    slippage,
)
