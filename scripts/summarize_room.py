"""One short line per Step 8 variant. Usage: py scripts\\summarize_room.py research_2022_25"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def _fmt(b):
    return f"n={b['n']} {b['expectancy_r']:+.3f}R dip={b['drawdown_r']:.1f}R"


def main():
    name = sys.argv[1]
    base = ROOT / "results" / "lock3"
    if (base / f"{name}_hunt.txt").exists():
        print(f"{name} baseline (no Step 8)")
        print("  hunt   " + _fmt(_load(base / f"{name}_hunt.txt")["combined"]))
        print("  switch " + _fmt(_load(base / f"{name}_switch.txt")["one_position"]))
    for hunt_path in sorted((ROOT / "results" / "room").glob(f"{name}_*_hunt.txt")):
        variant = hunt_path.name[len(name) + 1:-len("_hunt.txt")]
        print(variant)
        print("  hunt   " + _fmt(_load(hunt_path)["combined"]))
        print("  switch " + _fmt(_load(hunt_path.with_name(f"{name}_{variant}_switch.txt"))["one_position"]))


main()
