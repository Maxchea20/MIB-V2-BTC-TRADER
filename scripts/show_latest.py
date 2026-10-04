"""Show the latest lock and the newest result timestamps. Usage: py scripts\\show_latest.py"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = (
    "exp-hunt-desktop-cfi-floors",
    "exp-hunt-chop-floors",
    "exp-hunt-chop-boxcheck",
    "exp-hunt-desktop-cfi-v1",
    "exp-hunt-chop-arbiter",
)


def main():
    text = (ROOT / "config" / "experiments" / "LATEST.md").read_text(encoding="utf-8")
    name = re.search(r"Latest: \*\*(.+?)\*\*", text)
    when = re.search(r"Locked: \*\*(.+?)\*\*", text)
    print(f"Latest lock: {name.group(1) if name else '?'}")
    print(f"Locked at:   {when.group(1) if when else '?'}")
    print("Newest result files on this PC:")
    for folder in FOLDERS:
        runs = sorted((ROOT / "results" / folder).glob("*/trades.csv"))
        print(f"  {folder:<30} {runs[-1].parent.name if runs else 'none'}")


if __name__ == "__main__":
    main()
