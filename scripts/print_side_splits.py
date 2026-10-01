"""Print long and short splits for one experiment."""

import csv
import sys
from pathlib import Path


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "exp-mtf-4h-1h-15m-v1"
    folders = sorted(p for p in Path("results", name).glob("*") if (p / "long_short_stats.csv").exists())
    if not folders:
        raise SystemExit(f"no side file in results/{name}")
    for folder in folders:
        print(folder)
        for row in csv.DictReader((folder / "long_short_stats.csv").open(encoding="utf-8")):
            print(row["label"], row["trades"], row["expectancy_r"], row["win_rate"], row["profit_factor"])
        print()


if __name__ == "__main__":
    main()
