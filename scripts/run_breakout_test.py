"""Hunt V3 plus a breakout trade after each chop stop (a close through the line), traded in the break direction.

Three TP/SL sets for the breakout trade, all one position with Hunt V3:
  atr    stop 1.5 ATR, target 2.5 ATR (1h ATR)
  line   stop = the broken line (close back through it), target 2R
  trail  stop = the broken line, then a 1R trail behind the best price, no target
Usage: py scripts\\run_breakout_test.py research_2022_25
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(text):
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def _fmt(b):
    if not b.get("n"):
        return "n=0"
    return f"n={b['n']} {b['expectancy_r']:+.3f}R total={b['n'] * b['expectancy_r']:+.0f}R dip={b['drawdown_r']:.1f}R"


def main():
    name = sys.argv[1]
    base = _load((ROOT / "results" / "lock3" / f"{name}_switch.txt").read_text(encoding="utf-8", errors="replace"))
    out = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "backtest_hunt_chop.py"), f"backend/{name}.db", base["hunt_file"], "breakout"],
        capture_output=True, text=True, cwd=ROOT, check=True,
    ).stdout
    res = _load(out)
    print(f"{name} Hunt V3 + breakout after chop stop")
    print("  Hunt V3          " + _fmt(res["base"]))
    for mode, label in (("atr", "ATR 1.5/2.5"), ("line", "line, 2R"), ("trail", "line, 1R trail")):
        t = res["breakout_tests"][mode]
        print(f"  breakout {label:<14} alone {_fmt(t['breakout_alone'])}")
        print(f"      Hunt V3 + it  {_fmt(t['combined'])} breakouts taken={t['combined'].get('brk', 0)}")


main()
