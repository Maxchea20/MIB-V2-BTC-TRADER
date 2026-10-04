"""Run the floors (or the eye) inside the full engine, then Hunt V3 on top. Real entry order, one position, chop book.

Modes (see src/btc_research/setups/hunt_exits.py):
  floors  floor at +1R once the best price is 1.75 ATR, floor at +2.0 ATR once it is 2.25 ATR
  eye2    the same floors with no cushion (1.5 / 2.0 ATR) plus the eye from 1.5 ATR on
Needs the saved Hunt V3 run for the same file (scripts\\run_lock3_all.bat) for the comparison lines.
Usage: py scripts\\run_floor_v3.py research_binance floors [realfill]
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(text):
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def _fmt(b):
    total = b["n"] * b["expectancy_r"]
    return f"n={b['n']} {b['expectancy_r']:+.3f}R total={total:+.0f}R dip={b['drawdown_r']:.1f}R R/dip={total / abs(b['drawdown_r']):.1f}"


def _run(*args):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=ROOT, check=True).stdout


def main():
    name, mode = sys.argv[1], sys.argv[2]
    extra = [a for a in sys.argv[3:] if a == "realfill"]
    tag = mode + ("-realfill" if extra else "")
    saved_hunt = _load((ROOT / "results" / "lock3" / f"{name}_hunt.txt").read_text(encoding="utf-8", errors="replace"))
    saved_v3 = _load((ROOT / "results" / "lock3" / f"{name}_switch.txt").read_text(encoding="utf-8", errors="replace"))
    hunt = _load(_run(str(ROOT / "scripts" / "backtest_desktop_cfi.py"), f"backend/{name}.db", mode, *extra))
    v3 = _load(_run(str(ROOT / "scripts" / "backtest_hunt_chop.py"), f"backend/{name}.db", hunt["file"], f"tag={tag}"))
    print(f"{name} {tag} inside the full engine")
    print("  Hunt alone, now   " + _fmt(saved_hunt["combined"]))
    print(f"  Hunt alone, {mode:<6}" + _fmt(hunt["combined"]))
    print("  Hunt V3, now      " + _fmt(saved_v3["one_position"]))
    print(f"  Hunt V3, {mode:<9}" + _fmt(v3["one_position"]) + f" hunt={v3['one_position']['hunt']} chop={v3['one_position']['chop']}")


if __name__ == "__main__":
    main()
