"""Chop book alone (it always used the real next-1m-open fill), from the saved Hunt V3 runs. Usage: py scripts\\show_chop.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for name in ("research_2019_21", "research_2022_25", "research_binance"):
    path = ROOT / "results" / "lock3" / f"{name}_switch.txt"
    if not path.exists():
        print(f"{name}: no saved run")
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    c = json.loads(text[text.index("{"):text.rindex("}") + 1])["chop"]
    if not c.get("n"):
        print(f"{name}: no chop trades")
        continue
    total = c["n"] * c["expectancy_r"]
    print(f"{name}: chop alone n={c['n']} avg {c['expectancy_r']:+.3f}R total {total:+.0f}R dip {c['drawdown_r']:.1f}R")
