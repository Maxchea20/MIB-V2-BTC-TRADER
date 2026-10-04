"""Does the box filter peek at the 1h bar still forming? Runs Hunt V3 with the old reading and the fixed one.

old   the box state of the 1h bar that contains the entry (that bar is not finished yet: up to 1 hour of future)
fixed the box state of the last 1h bar that had closed at the entry (what you would see live)
Usage: py scripts\\run_box_lag_check.py research_2022_25 [floors]
Without `floors` it uses the Hunt file from your Hunt V3 run; with it, the newest floors Hunt file for that period.
"""

import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YEAR = {"research_2019_21": "2020", "research_2022_25": "2022", "research_binance": "2025"}


def _load(text):
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def _fmt(b):
    total = b["n"] * b["expectancy_r"]
    return f"n={b['n']} {b['expectancy_r']:+.3f}R total={total:+.0f}R dip={b['drawdown_r']:.1f}R R/dip={total / abs(b['drawdown_r']):.1f}"


def _first_year(path):
    with path.open(encoding="utf-8") as handle:
        row = next(csv.DictReader(handle), None)
    return datetime.fromtimestamp(int(row["entry_time"]) / 1000, timezone.utc).strftime("%Y") if row else ""


def main():
    name = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2] == "floors":
        files = [f for f in sorted((ROOT / "results" / "exp-hunt-desktop-cfi-floors").glob("*/trades.csv")) if _first_year(f) == YEAR[name]]
        hunt_file, label = str(files[-1]), "floors Hunt file"
    else:
        hunt_file = _load((ROOT / "results" / "lock3" / f"{name}_switch.txt").read_text(encoding="utf-8", errors="replace"))["hunt_file"]
        label = "Hunt V3 Hunt file"
    print(f"{name}, {label}")
    for tag, extra in (("old (peeks at the forming bar)", ["box-leak"]), ("fixed (closed bars only)", [])):
        out = subprocess.run([sys.executable, str(ROOT / "scripts" / "backtest_hunt_chop.py"), f"backend/{name}.db", hunt_file, "tag=boxcheck", *extra],
                             capture_output=True, text=True, cwd=ROOT, check=True).stdout
        res = _load(out)
        print(f"  {tag}")
        print("    Hunt outside the box " + _fmt(res["hunt_outside_box"]))
        print("    Hunt V3              " + _fmt(res["one_position"]))


if __name__ == "__main__":
    main()
