"""Floors and the eye. The engine walk must give the same R as the replay in scripts/test_hunt_eye2.py."""

import importlib.util
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.data.loader import Bar
from btc_research.setups import hunt_exits


def _replay_module():
    spec = importlib.util.spec_from_file_location("eye2", ROOT / "scripts" / "test_hunt_eye2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bars(seed, n=4000):
    random.seed(seed)
    price, out = 100.0, []
    for i in range(n):
        o = price
        price = max(1.0, price + random.gauss(0, 0.12))
        out.append(Bar(i * 60_000, i * 60_000 + 60_000, o, max(o, price) + random.random() * 0.1, min(o, price) - random.random() * 0.1, price, 1.0))
    return out


def _trade(bars, i, side):
    entry = bars[i].open
    atr = 0.8
    sign = 1 if side == "LONG" else -1
    return {"side": side, "entry": entry, "stop": entry - sign * 1.5 * atr, "target": entry + sign * 2.5 * atr,
            "atr": atr, "risk": 1.5 * atr, "entry_time": bars[i].open_time}


class HuntExitsTest(unittest.TestCase):
    def test_walk_matches_replay(self):
        eye2 = _replay_module()
        cfgs = {"floors": dict(tiers=((1.75, 1.5), (2.25, 2.0))), "eye2": dict(eye2.SCHEMES)["zones + eye .2"]}
        compared = 0
        for seed in range(6):
            bars = _bars(seed)
            for i in range(10, 3000, 150):
                for side in ("LONG", "SHORT"):
                    trade = _trade(bars, i, side)
                    for mode, cfg in cfgs.items():
                        want, reason, _ = eye2.replay(bars, i, {"side": side, "entry": trade["entry"], "stop": trade["stop"]}, cfg)
                        if reason == "TIME":
                            continue
                        done = hunt_exits.walk(dict(trade), bars, bars[i].open_time, bars[-1].open_time + 60_000, mode)
                        self.assertIsNotNone(done)
                        self.assertAlmostEqual(done["r_multiple"], want, places=9)
                        compared += 1
        self.assertGreater(compared, 100)

    def test_trade_still_open_returns_none(self):
        bars = _bars(1, 50)
        trade = _trade(bars, 0, "LONG")
        trade["stop"], trade["target"] = trade["entry"] - 50, trade["entry"] + 50
        self.assertIsNone(hunt_exits.walk(trade, bars, bars[0].open_time, bars[-1].open_time + 60_000, "floors"))

    def test_floor_turns_a_fade_into_a_win(self):
        # runs to about 2.4 ATR then falls back through everything: the 2.0 ATR floor closes it in profit
        bars, price = [], 100.0
        steps = [0.05] * 48 + [-0.05] * 100
        for i, d in enumerate(steps):
            o = price
            price += d
            bars.append(Bar(i * 60_000, i * 60_000 + 60_000, o, max(o, price) + 0.01, min(o, price) - 0.01, price, 1.0))
        trade = {"side": "LONG", "entry": 100.0, "stop": 98.5, "target": 102.5, "atr": 1.0, "risk": 1.5, "entry_time": 0}
        done = hunt_exits.walk(trade, bars, 0, bars[-1].open_time + 60_000, "floors")
        self.assertEqual(done["exit_reason"], "FLOOR")
        self.assertGreater(done["r_multiple"], 1.2)

    def test_trail_without_target_lets_a_run_go(self):
        # runs to about +4R, then falls back: with no target and a 1R trail it sells near +3R, not at +1.67R
        bars, price = [], 100.0
        steps = [0.1] * 60 + [-0.1] * 100
        for i, d in enumerate(steps):
            o = price
            price += d
            bars.append(Bar(i * 60_000, i * 60_000 + 60_000, o, max(o, price) + 0.01, min(o, price) - 0.01, price, 1.0))
        trade = {"side": "LONG", "entry": 100.0, "stop": 98.5, "target": 102.5, "atr": 1.0, "risk": 1.5, "entry_time": 0}
        cfg = dict(tiers=(), notarget=True, trail=(0.0, 1.5))
        done = hunt_exits.walk(dict(trade), bars, 0, bars[-1].open_time + 60_000, cfg)
        self.assertGreater(done["r_multiple"], 2.5)
        capped = hunt_exits.walk(dict(trade), bars, 0, bars[-1].open_time + 60_000, dict(tiers=()))
        self.assertEqual(capped["exit_reason"], "TARGET")


if __name__ == "__main__":
    unittest.main()
