"""Hunt V3 with the Hunt book limited to some UTC hours. The chop book is unchanged.

Uses the saved Hunt file, so no new Hunt run. Usage: py scripts\\run_hours_test.py research_2022_25 12-16
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(text):
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def _fmt(b):
    return f"n={b['n']} {b['expectancy_r']:+.3f}R total={b['n'] * b['expectancy_r']:+.0f}R dip={b['drawdown_r']:.1f}R"


def main():
    name, hours = sys.argv[1], sys.argv[2]
    base = _load((ROOT / "results" / "lock3" / f"{name}_switch.txt").read_text(encoding="utf-8", errors="replace"))
    out = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "backtest_hunt_chop.py"), f"backend/{name}.db", base["hunt_file"], f"hunt-hours={hours}"],
        capture_output=True, text=True, cwd=ROOT, check=True,
    ).stdout
    res = _load(out)
    one = res["one_position"]
    print(f"{name} Hunt only {hours} UTC (chop any hour)")
    print("  Hunt V3      " + _fmt(base["one_position"]))
    print("  this test    " + _fmt(one) + f" hunt={one['hunt']} chop={one['chop']}")


main()
