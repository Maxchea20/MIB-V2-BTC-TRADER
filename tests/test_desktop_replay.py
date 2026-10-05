"""The desktop Hunt replay: closed candles only, no future data, fills after the signal. Skipped when the desktop repo or numpy is not available."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.append(str(ROOT / "scripts"))
sys.path.append(str(ROOT / "tests"))

try:
    import desktop_hunt_replay as R
    D = R.load_desktop(R.find_desktop(None))
except (SystemExit, ImportError, ModuleNotFoundError) as exc:      # no desktop checkout or no numpy here
    R, D = None, None
    SKIP = str(exc)

from btc_research.execution import ExecutionConfig  # noqa: E402

DAY = 86_400_000


@unittest.skipIf(R is None, "desktop repo / numpy not available")
class DesktopReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_execution_engine import synthetic
        cls.bars = synthetic(70, 29)
        cls.feed = R.Feed(cls.bars)
        cls.start = cls.bars[0].open_time + 56 * DAY
        cls.end = cls.start + 4 * DAY

    def test_windows_hold_only_candles_that_had_closed(self):
        for t in range(self.start, self.end, 7 * 300_000):
            T = (t // 300_000) * 300_000
            for tf, limit in (("1m", 400), ("5m", 960), ("15m", 320), ("1h", 400), ("4h", 300)):
                rows = self.feed.window(tf, T, limit)
                self.assertTrue(rows)
                span = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400}[tf]
                self.assertLessEqual(rows[-1]["ts"] + span, T // 1000)       # its close time is not after T
                self.assertLessEqual(len(rows), limit)

    def test_no_future_data_cutting_the_data_never_changes_earlier_fires(self):
        full, _ = R.generate_fires(D, self.feed, self.start, self.end)
        self.assertGreater(len(full), 3)
        cut_at = self.start + 2 * DAY
        cut_bars = [b for b in self.bars if b.close_time <= cut_at]
        cut, _ = R.generate_fires(D, R.Feed(cut_bars), self.start, cut_at)
        key = lambda fs: [(f["T"], f["side"], round(f["entry"], 6), f["path"]) for f in fs if f["T"] < cut_at]
        self.assertEqual(key(full), key(cut))

    def test_realistic_fills_come_after_the_fire_and_the_live_guards_hold(self):
        fires, _ = R.generate_fires(D, self.feed, self.start, self.end)
        cfg = ExecutionConfig()
        times = [b.open_time for b in self.bars]
        trades, blocked = R.run_model(D, self.feed, self.bars, times, fires, "REALISTIC", cfg)
        self.assertGreater(len(trades), 3)
        last_exit = 0
        for t in trades:
            self.assertGreaterEqual(t["entry_time"], t["signal_time"] + cfg.latency_ms)
            self.assertGreater(t["exit_time"], t["entry_time"])
            self.assertGreaterEqual(t["signal_time"], last_exit)             # one position at a time
            last_exit = t["exit_time"]
            self.assertTrue((t["side"] == "LONG") == (t["entry"] > t["entry_raw"]))      # slippage against the trade
        for f, why in blocked:
            self.assertIn(why, ("POSITION_OPEN", "WEATHER_BLOCK", "COOLDOWN", "NOT_FILLED_OR_OPEN_AT_END"))

    def test_replay_is_deterministic(self):
        a, _ = R.generate_fires(D, self.feed, self.start, self.start + DAY)
        b, _ = R.generate_fires(D, self.feed, self.start, self.start + DAY)
        self.assertEqual([(f["T"], f["side"], f["path"]) for f in a], [(f["T"], f["side"], f["path"]) for f in b])


if __name__ == "__main__":
    unittest.main()
