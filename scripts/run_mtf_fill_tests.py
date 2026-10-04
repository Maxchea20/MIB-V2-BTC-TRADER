"""Lock 1 (4h trend, 1h break, 15m break) with honest fills. Runs the old config and six new ones and prints one line each.
  legacy        15m bar must CLOSE beyond the level, then the fill is booked at the level inside that bar (a past price: not tradable)
  nextopen      same signal, fill at the first 1m open after the 15m close (real)
  touch         resting stop order at the level, fills on first touch, no waiting for the close (real, every touch counts)
  stop sizes    15m = 1.5 x 15m ATR (scalp size), 4h-2R / 4h-4R = stop 1.5 x 4h ATR, target 3 / 6 x 4h ATR
Usage: py scripts\\run_mtf_fill_tests.py [backend\\research_2022_25.db]
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["exp-mtf-4h-1h-15m-v1"] + [f"exp-mtf-{m}-{t}" for m in ("nextopen", "touch") for t in ("15m", "4h-2R", "4h-4R")]


def main():
    db = sys.argv[1:]
    for name in NAMES:
        cmd = [sys.executable, str(ROOT / "scripts" / "backtest.py"), "--experiment", name] + (["--db", db[0]] if db else [])
        out = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT).stdout
        try:
            s = json.loads(out[out.index("{"):out.rindex("}") + 1])
        except ValueError:
            print(f"{name:<26} failed")
            continue
        n = s["trades"]
        total = n * s["net_expectancy_r"]
        print(f"{name:<26} n={n:4d} avg {s['net_expectancy_r']:+.3f}R total {total:+.0f}R PF {s['profit_factor']:.2f} win {s['win_rate']:.0%} dip {s['max_drawdown_r']:.1f}R")


if __name__ == "__main__":
    main()
