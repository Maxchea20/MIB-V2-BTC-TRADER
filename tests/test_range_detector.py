"""Range detector cases. No orders."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from btc_research.market_structure.range_detector import detect_range, react


def bars(rows):
    return [{"open_time": i, "high": h, "low": l, "close": c} for i, (h, l, c) in enumerate(rows)]


def box(n=80):
    rows = []
    for i in range(n):
        if i % 8 < 4:
            rows.append((110, 100, 101 + (i % 4)))
        else:
            rows.append((110.2, 100.1, 108 - (i % 4)))
    return bars(rows)


class RangeDetectorTest(unittest.TestCase):
    def test_clean_horizontal_range(self):
        state = detect_range(box())
        self.assertTrue(state.active)
        self.assertGreater(state.high, state.low)
        self.assertGreaterEqual(state.containment, 0.75)
        self.assertLessEqual(state.efficiency, 0.30)
        self.assertGreaterEqual(state.upper_touches, 2)
        self.assertGreaterEqual(state.lower_touches, 2)
        self.assertEqual(state.phase, "RANGE")

    def test_strong_uptrend(self):
        state = detect_range(bars([(100 + i, 99 + i, 99.6 + i) for i in range(80)]))
        self.assertFalse(state.active)

    def test_strong_downtrend(self):
        state = detect_range(bars([(200 - i, 199 - i, 199.4 - i) for i in range(80)]))
        self.assertFalse(state.active)

    def test_upper_failed_break(self):
        rows = box()
        rows[-2] = {"open_time": 78, "high": 116, "low": 105, "close": 109}
        state = detect_range(rows)
        self.assertGreaterEqual(state.failed_breaks, 1)
        self.assertEqual(react(state, rows[-2]), "RANGE")

    def test_lower_failed_break(self):
        rows = box()
        rows[-2] = {"open_time": 78, "high": 106, "low": 94, "close": 102}
        state = detect_range(rows)
        self.assertGreaterEqual(state.failed_breaks, 1)
        self.assertEqual(react(state, rows[-2]), "RANGE")

    def test_breakout_escapes(self):
        state = detect_range(box())
        outside = {"high": 116, "low": 111, "close": 114}
        self.assertEqual(react(state, outside), "BREAKOUT_CANDIDATE")
        self.assertEqual(react(state, outside, "BREAKOUT_CANDIDATE"), "BREAKOUT_CONFIRMED")
        back = {"high": 111, "low": 104, "close": 106}
        self.assertEqual(react(state, back, "BREAKOUT_CANDIDATE"), "RANGE_REJECTION")


if __name__ == "__main__":
    unittest.main()
