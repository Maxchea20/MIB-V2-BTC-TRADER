"""Execution simulator: could this order really have been filled, and at what price?"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.data.loader import Bar
from btc_research.data.resample import resample
from btc_research.execution import ExecutionConfig, limit_fill, liquidation_price, market_fill, resolve_bar, slippage

MIN = 60_000


def bar(minute, o, h=None, l=None, c=None):
    h = h if h is not None else max(o, c if c is not None else o)
    l = l if l is not None else min(o, c if c is not None else o)
    return Bar(minute * MIN, (minute + 1) * MIN, o, h, l, c if c is not None else o, 1.0)


def flat(minutes, price):
    return [bar(m, price) for m in minutes]


CFG = ExecutionConfig()


class MarketOrders(unittest.TestCase):
    def test_a_price_moved_away_is_not_filled_at_the_level(self):
        bars = flat(range(0, 10), 100_000.0) + [bar(10, 100_500.0)] + flat(range(11, 15), 100_500.0)
        times = [b.open_time for b in bars]
        protected = CFG.with_(max_entry_slippage_bps=5.0)
        f = market_fill(bars, times, "LONG", 10 * MIN, protected, entering=True, intended=100_000.0)
        self.assertEqual(f.status, "MISSED_FILL")
        self.assertEqual(f.reason, "PRICE_MOVED_AWAY")
        plain = market_fill(bars, times, "LONG", 10 * MIN, CFG, entering=True, intended=100_000.0)
        self.assertEqual(plain.status, "FILLED")
        self.assertGreater(plain.fill_price, 100_500.0)      # never the 100,000 level
        self.assertEqual(plain.fill_time, 10 * MIN)

    def test_b_reachable_price_fills_at_the_next_open_plus_slippage(self):
        bars = flat(range(0, 12), 100_000.0)
        times = [b.open_time for b in bars]
        f = market_fill(bars, times, "LONG", 10 * MIN, CFG.with_(max_entry_slippage_bps=5.0), entering=True, intended=100_000.0)
        self.assertEqual(f.status, "FILLED")
        self.assertAlmostEqual(f.fill_price, 100_000.0 + slippage(100_000.0, CFG, True))
        self.assertEqual(f.fill_time, 10 * MIN)

    def test_latency_moves_the_fill_to_the_next_1m_open(self):
        bars = [bar(m, 100.0 + m) for m in range(0, 20)]
        times = [b.open_time for b in bars]
        at_close = market_fill(bars, times, "LONG", 10 * MIN, CFG, True)
        late = market_fill(bars, times, "LONG", 10 * MIN + 1_000, CFG, True)      # 1 s after the signal close
        self.assertEqual(at_close.fill_time, 10 * MIN)
        self.assertEqual(late.fill_time, 11 * MIN)
        self.assertGreater(late.fill_time, late.submit_time)

    def test_end_of_data_is_a_missed_fill_not_a_silent_drop(self):
        bars = flat(range(0, 5), 100.0)
        f = market_fill(bars, [b.open_time for b in bars], "SHORT", 9 * MIN, CFG, True)
        self.assertEqual((f.status, f.reason), ("MISSED_FILL", "NO_DATA"))


class LimitOrders(unittest.TestCase):
    def test_c_price_touched_before_the_order_existed_does_not_fill(self):
        bars = flat(range(0, 4), 101.0) + [bar(4, 101.0, 101.0, 99.0, 101.0)] + flat(range(5, 20), 101.0)   # dipped to 99 in minute 4
        times = [b.open_time for b in bars]
        f = limit_fill(bars, times, "LONG", 100.0, 5 * MIN, CFG, entering=True)
        self.assertEqual(f.status, "MISSED_FILL")
        # a bar that opened before the submit time is not eligible even if it traded through later in the minute
        f2 = limit_fill(bars, times, "LONG", 100.0, 4 * MIN + 30_000, CFG, entering=True)
        self.assertEqual(f2.status, "MISSED_FILL")

    def test_d_untouched_limit_is_a_missed_fill(self):
        bars = flat(range(0, 30), 101.0)
        times = [b.open_time for b in bars]
        self.assertEqual(limit_fill(bars, times, "LONG", 100.0, 5 * MIN, CFG, True).reason, "NOT_REACHED")
        self.assertEqual(limit_fill(bars, times, "LONG", 100.0, 5 * MIN, CFG, True, ttl_ms=3 * MIN).reason, "EXPIRED")

    def test_e_limit_reached_after_submission_fills_at_the_limit(self):
        bars = flat(range(0, 7), 101.0) + [bar(7, 101.0, 101.0, 99.8, 100.5)] + flat(range(8, 12), 101.0)
        times = [b.open_time for b in bars]
        f = limit_fill(bars, times, "LONG", 100.0, 5 * MIN, CFG, True)
        self.assertEqual(f.status, "FILLED")
        self.assertEqual(f.fill_price, 100.0)
        self.assertEqual(f.liquidity, "maker")
        self.assertGreaterEqual(f.fill_time, f.submit_time)

    def test_a_bare_touch_is_not_enough(self):
        bars = flat(range(0, 7), 101.0) + [bar(7, 101.0, 101.0, 100.0, 100.5)] + flat(range(8, 12), 101.0)
        times = [b.open_time for b in bars]
        self.assertEqual(limit_fill(bars, times, "LONG", 100.0, 5 * MIN, CFG, True).status, "MISSED_FILL")
        self.assertEqual(limit_fill(bars, times, "LONG", 100.0, 5 * MIN, CFG.with_(limit_trade_through_ticks=0.0), True).status, "FILLED")

    def test_marketable_limit_fills_as_a_taker_capped_at_the_limit(self):
        bars = flat(range(0, 12), 99.0)
        times = [b.open_time for b in bars]
        f = limit_fill(bars, times, "LONG", 100.0, 5 * MIN, CFG, True)
        self.assertEqual((f.status, f.liquidity), ("FILLED", "taker"))
        self.assertLessEqual(f.fill_price, 100.0)


class RestingExits(unittest.TestCase):
    def setUp(self):
        self.both = bar(10, 100.0, 101.2, 98.9, 100.0)     # touches stop 99 and target 101 in one minute

    def test_f_same_bar_stop_and_target_follows_the_policy(self):
        r = resolve_bar(self.both, "LONG", 99.0, 101.0, CFG)
        self.assertEqual(r["reason"], "STOP")
        self.assertEqual(resolve_bar(self.both, "LONG", 99.0, 101.0, CFG), r)           # deterministic
        self.assertEqual(resolve_bar(self.both, "LONG", 99.0, 101.0, CFG.with_(intrabar_policy="optimistic"))["reason"], "TARGET")
        self.assertEqual(resolve_bar(self.both, "LONG", 99.0, 101.0, CFG.with_(intrabar_policy="unresolved"))["reason"], "UNRESOLVED_BOTH_HIT")
        short = bar(10, 100.0, 101.2, 98.9, 100.0)
        self.assertEqual(resolve_bar(short, "SHORT", 101.0, 99.0, CFG)["reason"], "STOP")

    def test_gap_through_the_stop_fills_at_the_open_not_the_stop(self):
        gap = bar(10, 98.0, 98.5, 97.5, 98.0)
        r = resolve_bar(gap, "LONG", 99.0, 102.0, CFG)
        self.assertEqual(r["reason"], "STOP")
        self.assertEqual(r["raw"], 98.0)
        self.assertLess(r["fill"], 98.0)
        self.assertEqual(r["time"], gap.open_time)

    def test_target_needs_a_trade_through_and_fills_at_the_limit_price(self):
        touch = bar(10, 100.0, 101.0, 99.5, 100.5)
        self.assertIsNone(resolve_bar(touch, "LONG", 99.0, 101.0, CFG))                 # touched, not traded through
        through = bar(10, 100.0, 101.2, 99.5, 100.5)
        r = resolve_bar(through, "LONG", 99.0, 101.0, CFG)
        self.assertEqual((r["reason"], r["fill"]), ("TARGET", 101.0))
        self.assertEqual(r["time"], through.close_time)

    def test_g_long_and_short_are_side_correct(self):
        bars = flat(range(0, 12), 100.0)
        times = [b.open_time for b in bars]
        self.assertGreater(market_fill(bars, times, "LONG", 5 * MIN, CFG, True).fill_price, 100.0)     # a long buys: worse is higher
        self.assertLess(market_fill(bars, times, "SHORT", 5 * MIN, CFG, True).fill_price, 100.0)       # a short sells: worse is lower
        self.assertLess(market_fill(bars, times, "LONG", 5 * MIN, CFG, False).fill_price, 100.0)       # closing a long sells
        self.assertGreater(market_fill(bars, times, "SHORT", 5 * MIN, CFG, False).fill_price, 100.0)   # closing a short buys
        stop_long = resolve_bar(bar(10, 100, 100, 98, 98), "LONG", 99.0, 105.0, CFG)
        stop_short = resolve_bar(bar(10, 100, 102, 100, 102), "SHORT", 101.0, 95.0, CFG)
        self.assertLess(stop_long["fill"], 99.0)
        self.assertGreater(stop_short["fill"], 101.0)
        # short entry limit is a SELL: reached when price trades up through it
        up = flat(range(0, 6), 99.0) + [bar(6, 99.0, 100.3, 99.0, 99.5)] + flat(range(7, 10), 99.0)
        f = limit_fill(up, [b.open_time for b in up], "SHORT", 100.0, 5 * MIN, CFG, True)
        self.assertEqual((f.status, f.fill_price), ("FILLED", 100.0))

    def test_h_slippage_values(self):
        cfg = ExecutionConfig(entry_slippage_bps=0.5, exit_slippage_bps=1.0, slippage_ticks=1.0, tick_size=0.1)
        self.assertAlmostEqual(slippage(100_000.0, cfg, True), 0.1 + 5.0)
        self.assertAlmostEqual(slippage(100_000.0, cfg, False), 0.1 + 10.0)
        bars = flat(range(0, 12), 100_000.0)
        times = [b.open_time for b in bars]
        self.assertAlmostEqual(market_fill(bars, times, "LONG", 5 * MIN, cfg, True).fill_price, 100_000.0 + 5.1)
        self.assertAlmostEqual(market_fill(bars, times, "LONG", 5 * MIN, cfg, False).fill_price, 100_000.0 - 10.1)

    def test_liquidation_is_side_correct_and_off_by_default(self):
        self.assertIsNone(liquidation_price("LONG", 100.0, CFG))
        cfg = CFG.with_(leverage=10.0, maintenance_margin_rate=0.004)
        self.assertLess(liquidation_price("LONG", 100.0, cfg), 100.0)
        self.assertGreater(liquidation_price("SHORT", 100.0, cfg), 100.0)


class NoFutureData(unittest.TestCase):
    def test_i_adding_later_bars_never_changes_a_fill_already_made(self):
        bars = flat(range(0, 7), 101.0) + [bar(7, 101.0, 101.0, 99.8, 100.5)] + [bar(m, 90.0 + m) for m in range(8, 40)]
        times = [b.open_time for b in bars]
        full = limit_fill(bars, times, "LONG", 100.0, 5 * MIN, CFG, True)
        cut = bars[:8]
        part = limit_fill(cut, [b.open_time for b in cut], "LONG", 100.0, 5 * MIN, CFG, True)
        self.assertEqual((full.status, full.fill_time, full.fill_price), (part.status, part.fill_time, part.fill_price))
        m_full = market_fill(bars, times, "SHORT", 6 * MIN, CFG, True)
        m_cut = market_fill(bars[:7], [b.open_time for b in bars[:7]], "SHORT", 6 * MIN, CFG, True)
        self.assertEqual((m_full.fill_time, m_full.fill_price), (m_cut.fill_time, m_cut.fill_price))
        stop_full = resolve_bar(bars[7], "LONG", 99.9, 110.0, CFG)
        self.assertEqual(stop_full, resolve_bar(bars[7], "LONG", 99.9, 110.0, CFG))

    def test_j_an_unclosed_candle_does_not_exist(self):
        ones = [bar(m, 100.0 + m) for m in range(0, 8)]        # minutes 0-4 close one 5m candle, minutes 5-7 are an unfinished one
        five = resample(ones, "5m")
        self.assertEqual([b.open_time for b in five], [0])
        self.assertEqual(five[-1].close_time, 5 * MIN)


if __name__ == "__main__":
    unittest.main()
