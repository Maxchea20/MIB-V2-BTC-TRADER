"""Synthetic causal check. Does not read a database."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.data.loader import Bar
from btc_research.data.resample import resample
from btc_research.structure import swing_points


def main() -> None:
    bars = []
    price = 100.0
    for i in range(300):
        drift = 0.2 if i < 180 else -0.05
        o = price
        c = price + drift
        bars.append(Bar(i * 60_000, (i + 1) * 60_000, o, max(o, c) + 0.1, min(o, c) - 0.1, c, 1))
        price = c
    bars_1h = resample(bars, "1h")
    highs, lows = swing_points([b.high for b in bars_1h], [b.low for b in bars_1h], 1, 1)
    for pivot in highs + lows:
        assert pivot.confirm_index > pivot.index
    assert bars_1h[-1].close_time <= bars[-1].close_time
    print("self_check_ok")


if __name__ == "__main__":
    main()
