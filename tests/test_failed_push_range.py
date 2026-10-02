"""Failed-push range cases. No orders."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from btc_research.market_structure.failed_push_range import detect_push_range


def b(o, h, l, c):
    return {"open": o, "high": h, "low": l, "close": c}


def leg(start, end, n=6):
    rows = []
    for i in range(n):
        price = start + (end - start) * i / (n - 1)
        rows.append(b(price, price + 0.3, price - 0.3, price))
    return rows


def box():
    rows = []
    rows += leg(100, 110)
    rows[-1] = b(109, 110, 108, 109.2)
    rows += leg(109, 100)
    rows[-1] = b(101, 102, 100, 101)
    rows += leg(101, 106)
    rows[-1] = b(105, 106, 104, 105.2)
    rows += leg(105, 101)
    rows[-1] = b(102, 103, 101, 102)
    rows += leg(102, 105)
    rows[-1] = b(104, 105, 103, 104.2)
    rows += [b(103, 104, 102, 103.2)] * 8
    return rows


class FailedPushRangeTest(unittest.TestCase):
    def test_two_failed_pushes_draw_the_box(self):
        state = detect_push_range(box())
        self.assertTrue(state.active)
        self.assertAlmostEqual(state.high, 106)
        self.assertAlmostEqual(state.low, 100)
        self.assertEqual(state.phase, "RANGE")

    def test_wick_does_not_end_the_box(self):
        self.assertEqual(detect_push_range(box() + [b(104, 108, 103, 104)]).phase, "RANGE")

    def test_solid_close_is_only_a_candidate(self):
        self.assertEqual(detect_push_range(box() + [b(105, 109, 104.5, 108.5)]).phase, "BREAKOUT_CANDIDATE")

    def test_return_inside_expands_the_line(self):
        rows = box() + [b(105, 109, 104.5, 108.5), b(108, 108.2, 103, 104)]
        state = detect_push_range(rows)
        self.assertEqual(state.phase, "RANGE")
        self.assertAlmostEqual(state.high, 109)
        self.assertAlmostEqual(state.low, 100)

    def test_second_solid_close_confirms_the_break(self):
        rows = box() + [b(105, 109, 104.5, 108.5), b(108.5, 110, 107.5, 109.5)]
        state = detect_push_range(rows)
        self.assertEqual(state.phase, "BREAKOUT_CONFIRMED")
        self.assertFalse(state.active)

    def test_trend_is_not_a_box(self):
        self.assertFalse(detect_push_range([b(100 + i, 101 + i, 99 + i, 100.6 + i) for i in range(40)]).active)


if __name__ == "__main__":
    unittest.main()
