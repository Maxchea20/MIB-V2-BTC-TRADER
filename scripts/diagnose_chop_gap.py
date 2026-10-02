"""How far the chop stop and target sat from the entry."""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "exp-chop-push-1h"
    files = sorted((ROOT / "results" / name).glob("*/trades.csv"))
    if not files:
        raise SystemExit(f"no trades in {name}")
    rows = list(csv.DictReader(files[-1].open(encoding="utf-8")))
    ratios = []
    stop_bps = []
    for row in rows:
        entry = float(row["entry"])
        risk = abs(entry - float(row["stop"]))
        reward = abs(float(row["target"]) - entry)
        if risk <= 0:
            continue
        ratios.append(reward / risk)
        stop_bps.append(risk / entry * 10000)
    print(json.dumps({
        "file": str(files[-1]),
        "n": len(ratios),
        "median_reward_over_risk": round(sorted(ratios)[len(ratios) // 2], 4),
        "median_stop_bps": round(sorted(stop_bps)[len(stop_bps) // 2], 1),
    }, indent=2))


if __name__ == "__main__":
    main()
