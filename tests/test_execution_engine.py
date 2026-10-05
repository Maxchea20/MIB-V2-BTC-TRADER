"""Hunt engine + chop book with the execution simulator: no fake fills, no future data, every FIRE accounted for."""

import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.append(str(ROOT / "scripts"))   # appended, not first: scripts/test_hunt_exits.py is a script and must not shadow tests/test_hunt_exits.py

from btc_research.data.loader import Bar
from btc_research.data.resample import resample
from btc_research.execution import ExecutionConfig

import backtest_desktop_cfi as eng
import backtest_hunt_chop as hc

MIN = 60_000


def synthetic(days, seed):
    rnd = random.Random(seed)
    bars, p = [], 100_000.0
    t0 = 1_700_000_000_000 // 300_000 * 300_000
    for i in range(60 * 24 * days):
        block = (i // (60 * 24 * 6)) % 3
        d = rnd.gauss((0.0, 0.9, -0.9)[block], 35)
        o, c = p, p + d
        bars.append(Bar(t0 + i * MIN, t0 + (i + 1) * MIN, o, max(o, c) + rnd.random() * 12, min(o, c) - rnd.random() * 12, c, 1.0))
        p = c
    return bars


def run(bars, cfg, **kw):
    r = [resample(bars, x) for x in ("5m", "15m", "1h", "4h")]
    events = []
    trades = eng._run(bars, *r, False, None, False, "floors", False, cfg, events, **kw)
    return trades, events, r


class HuntExecution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bars = synthetic(40, 17)
        cls.cfg = ExecutionConfig()
        cls.trades, cls.events, cls.r = run(cls.bars, cls.cfg)

    def test_there_are_trades_to_check(self):
        self.assertGreater(len(self.trades), 30)

    def test_i_entry_is_never_before_the_order_could_exist(self):
        for t in self.trades:
            self.assertGreaterEqual(t["order_submit_time"], t["signal_time"] + self.cfg.latency_ms)
            self.assertGreaterEqual(t["fill_time"], t["order_submit_time"])
            self.assertEqual(t["entry_time"], t["fill_time"])
            self.assertEqual(t["fill_status"], "FILLED")
            self.assertTrue(t["fake_fill_removed"])

    def test_j_signal_time_is_the_close_of_a_closed_5m_candle(self):
        closes = {b.close_time for b in self.r[0]}
        self.assertLessEqual(self.r[0][-1].close_time, self.bars[-1].close_time)
        for t in self.trades:
            self.assertIn(t["signal_time"], closes)

    def test_g_h_entry_slippage_is_against_the_trade(self):
        for t in self.trades:
            sign = 1 if t["side"] == "LONG" else -1
            slip = 0.1 + t["entry_raw"] * 0.5 / 10_000
            self.assertAlmostEqual((t["entry"] - t["entry_raw"]) * sign, slip, places=6)
            self.assertAlmostEqual(t["entry_slippage"], slip, places=6)

    def test_h_exit_fills_follow_the_order_type(self):
        for t in self.trades:
            sign = 1 if t["side"] == "LONG" else -1
            if t["exit_reason"] == "TARGET":
                self.assertEqual(t["exit"], t["target"])                    # resting limit: filled at its price, no slippage
                self.assertEqual(t["exit_order_type"], "LIMIT")
            else:
                self.assertEqual(t["exit_order_type"], "STOP_MARKET")
                self.assertLess(t["exit"] * sign, t["exit_raw"] * sign)     # stop-market exits are filled worse than the trigger/open price
                self.assertGreater(t["exit_slippage"], 0)

    def test_every_fire_is_accounted_for_nothing_is_silently_dropped(self):
        statuses = {e["status"] for e in self.events}
        self.assertTrue(statuses <= {"ORDER_FILLED", "SKIPPED_POSITION_OPEN", "SKIPPED_PAUSE", "MISSED_FILL", "UNRESOLVED_BOTH_HIT"})
        filled = sum(e["status"] == "ORDER_FILLED" for e in self.events)
        self.assertIn(filled - len(self.trades), (0, 1))                    # at most the trade still open when the data ends
        for e in self.events:
            for k in ("signal_time", "signal_side", "signal_level", "signal_price"):
                self.assertIn(k, e)

    def test_a_a_missed_fill_is_recorded_not_traded(self):
        strict = ExecutionConfig(max_entry_slippage_bps=0.01)               # price protection so tight that almost every market order is refused
        trades, events, _ = run(self.bars, strict)
        missed = [e for e in events if e["status"] == "MISSED_FILL"]
        self.assertGreater(len(missed), 0)
        self.assertLess(len(trades), len(self.trades))
        self.assertTrue(all(e["reason"] == "PRICE_MOVED_AWAY" for e in missed))

    def test_the_old_fill_only_exists_behind_the_fakefill_flag(self):
        fake = eng._run(self.bars, *self.r, False, None, False, "floors", True)
        self.assertGreater(len(fake), 0)
        self.assertTrue(all(t["fill_reference"] == "LEVEL_FAKE" and not t["fake_fill_removed"] for t in fake))
        self.assertTrue(all(t["fake_fill_removed"] for t in self.trades))

    def test_latency_zero_with_idealised_exits_is_the_previous_real_fill(self):
        t0, _, _ = run(self.bars, ExecutionConfig(execution_latency_seconds=0.0), ideal_exits=True)
        self.assertTrue(all(t["fill_time"] == t["signal_time"] for t in t0))


class TrendGate(unittest.TestCase):
    """The optional 1H-trend gate and the 1H ATR unit. Both are off by default and must not change Hunt when off."""

    @classmethod
    def setUpClass(cls):
        cls.bars = synthetic(40, 17)
        cls.cfg = ExecutionConfig()
        cls.r = [resample(cls.bars, x) for x in ("5m", "15m", "1h", "4h")]

    def go(self, **kw):
        events = []
        trades = eng._run(self.bars, *self.r, False, None, False, "floors", False, self.cfg, events, False, **kw)
        return trades, events

    def test_off_by_default_changes_nothing(self):
        a, _ = self.go()
        b, _ = self.go(trend_gate=None, atr_unit="15m")
        key = lambda ts: [(t["signal_time"], t["entry"], t["exit"], t["r_multiple"]) for t in ts]
        self.assertEqual(key(a), key(b))

    def test_gated_trades_only_follow_the_closed_1h_trend(self):
        trades, events = self.go(trend_gate=("1h", 20))
        h1 = self.r[2]
        self.assertGreater(len(trades), 10)
        for t in trades:
            n = eng._closed(h1, t["signal_time"], 3_600_000)           # only 1H bars that had closed when the signal became known
            trend = "LONG" if h1[n - 1].close > h1[n - 21].close else "SHORT"
            self.assertEqual(t["side"], trend)
        filtered = [e for e in events if e["status"] == "FILTERED_TREND_GATE"]
        self.assertGreater(len(filtered), 0)                              # filtered FIREs are recorded, not dropped
        self.assertGreater(len(events), len(filtered))

    def test_1h_atr_unit_sizes_stop_and_target_from_the_1h_atr(self):
        trades, _ = self.go(atr_unit="1h")
        atr_1h = eng._atr(self.r[2])
        for t in trades[:50]:
            n = eng._closed(self.r[2], t["signal_time"], 3_600_000)
            self.assertAlmostEqual(t["atr"], atr_1h[n - 1])
            self.assertAlmostEqual(t["risk"], 1.5 * atr_1h[n - 1])
            sign = 1 if t["side"] == "LONG" else -1
            self.assertAlmostEqual((t["target"] - t["entry"]) * sign, 2.5 * atr_1h[n - 1])


class ChopExecution(unittest.TestCase):
    def setUp(self):
        self.cfg = ExecutionConfig()
        hc.EXEC = self.cfg

    def tearDown(self):
        hc.EXEC, hc.BARS_1M, hc.TIMES_1M = None, [], []

    def series(self, hour_closes, level=100_000.0):
        ones, hours = [], []
        for h, close in enumerate(hour_closes):
            for m in range(60):
                k = h * 60 + m
                ones.append(Bar(k * MIN, (k + 1) * MIN, level, level + 5, level - 5, level, 1.0))
            hours.append(Bar(h * 60 * MIN, (h + 1) * 60 * MIN, level, level + 5, level - 5, close, 1.0))
        return ones, hours

    def trade(self, entry_time):
        return {"book": "CHOP", "side": "LONG", "entry": 100_000.0, "stop": 99_000.0, "target": 100_900.0, "risk": 1_000.0,
                "entry_time": entry_time, "line_high": 100_900.0, "line_low": 99_000.0}

    def test_close_through_the_line_is_a_market_exit_after_the_close(self):
        ones, hours = self.series([100_000.0, 100_000.0, 98_500.0, 98_000.0])          # hour 2 closes through the line
        hc.BARS_1M, hc.TIMES_1M = ones, [b.open_time for b in ones]
        done = hc._walk(self.trade(60 * MIN), hours, 1)
        self.assertEqual(done["exit_reason"], "STOP")
        self.assertGreaterEqual(done["exit_time"], hours[2].close_time + self.cfg.latency_ms)    # not at the start of the bar, not at the line
        self.assertNotEqual(done["exit"], 99_000.0)
        self.assertLess(done["exit"], done["exit_raw"])                                           # sold a long: slippage against
        self.assertEqual(done["exit_order_type"], "MARKET")

    def test_target_inside_the_hour_is_filled_even_if_the_hour_later_closes_through_the_line(self):
        ones, hours = self.series([100_000.0, 98_000.0])
        hc.BARS_1M, hc.TIMES_1M = ones, [b.open_time for b in ones]
        k = 60 + 20                                                                      # minute 20 of hour 1 trades through the target
        ones[k] = Bar(k * MIN, (k + 1) * MIN, 100_000.0, 100_950.0, 99_990.0, 100_500.0, 1.0)
        done = hc._walk(self.trade(60 * MIN), hours, 1)
        self.assertEqual((done["exit_reason"], done["exit"]), ("TARGET", 100_900.0))
        self.assertEqual(done["exit_order_type"], "LIMIT")

    def test_a_bare_touch_of_the_target_is_not_a_fill(self):
        ones, hours = self.series([100_000.0, 100_000.0])
        hc.BARS_1M, hc.TIMES_1M = ones, [b.open_time for b in ones]
        k = 60 + 20
        ones[k] = Bar(k * MIN, (k + 1) * MIN, 100_000.0, 100_900.0, 99_990.0, 100_500.0, 1.0)     # high == target exactly
        self.assertIsNone(hc._walk(self.trade(60 * MIN), hours, 1))


if __name__ == "__main__":
    unittest.main()
