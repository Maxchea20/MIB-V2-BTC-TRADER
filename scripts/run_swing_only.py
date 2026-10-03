"""Doc steps 1-9 in full: Hunt only in swing weather, chop only in the box, nothing else.

Re-uses the Hunt file from the saved Lock 3 run, so there is no new Hunt run.
Usage: py scripts\\run_swing_only.py research_2022_25
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(text):
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def _fmt(b):
    return f"n={b['n']} {b['expectancy_r']:+.3f}R dip={b['drawdown_r']:.1f}R"


def main():
    name = sys.argv[1]
    hunt_run = _load((ROOT / "results" / "lock3" / f"{name}_hunt.txt").read_text(encoding="utf-8", errors="replace"))
    out = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "backtest_hunt_chop.py"), f"backend/{name}.db", hunt_run["file"], "swing-only"],
        capture_output=True, text=True, cwd=ROOT, check=True,
    ).stdout
    res = _load(out)
    one = res["one_position"]
    print(f"{name} swing-only Hunt + box chop")
    print("  swing Hunt " + _fmt(res["hunt"]))
    print("  chop       " + _fmt(res["chop"]))
    print("  combined   " + _fmt(one) + f" hunt={one['hunt']} chop={one['chop']}")


main()
