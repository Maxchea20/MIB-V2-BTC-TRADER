"""Command-line options shared by the engines: latency=1 entry-slip=0.5 exit-slip=0.5 fee=2 intrabar=conservative through=1"""

from __future__ import annotations

from btc_research.execution.simulator import ExecutionConfig

NAMES = {
    "latency": ("execution_latency_seconds", float),
    "entry-slip": ("entry_slippage_bps", float),
    "exit-slip": ("exit_slippage_bps", float),
    "fee": ("fee_bps_per_side", float),
    "intrabar": ("intrabar_policy", str),
    "through": ("limit_trade_through_ticks", float),
}


def config_from_args(args):
    """Returns (ExecutionConfig, the args that were not key=value execution options)."""
    kw, rest = {}, []
    for a in args:
        key, _, value = a.partition("=")
        if value and key in NAMES:
            name, cast = NAMES[key]
            kw[name] = cast(value)
        else:
            rest.append(a)
    return ExecutionConfig(**kw), rest
