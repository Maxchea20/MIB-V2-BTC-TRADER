"""One short line per research file from the saved Lock 3 runs in results/lock3."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def _fmt(label, b):
    return f"{label} n={b['n']} {b['expectancy_r']:+.3f}R dip={b['drawdown_r']:.1f}R"


def main():
    for hunt_path in sorted((ROOT / "results" / "lock3").glob("*_hunt.txt")):
        name = hunt_path.name[:-len("_hunt.txt")]
        hunt = _load(hunt_path)["combined"]
        sw = _load(hunt_path.with_name(f"{name}_switch.txt"))
        print(name)
        print("  " + _fmt("hunt  ", hunt) + f" pf={hunt['profit_factor']}")
        print("  " + _fmt("chop  ", sw["chop"]))
        print("  " + _fmt("switch", sw["one_position"]) + f" hunt={sw['one_position']['hunt']} chop={sw['one_position']['chop']}")


main()
