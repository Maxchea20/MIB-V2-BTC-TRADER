"""Print side split, exit mix, and cost drag for the latest S1 run."""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def num(row: dict, key: str) -> float:
    return float(row[key])


def block(rows: list[dict]) -> dict:
    closed = [row for row in rows if row["exit_reason"] != "END_OF_DATA"]
    if not closed:
        return {"n": 0}
    wins = [row for row in closed if num(row, "net_pnl") > 0]
    losses = [row for row in closed if num(row, "net_pnl") <= 0]
    stop_bps = [abs(num(row, "entry") - num(row, "stop")) / num(row, "entry") * 10_000 for row in closed]
    fee_r = [num(row, "fees") / max(1e-9, abs(num(row, "entry") - num(row, "stop"))) for row in closed]
    return {
        "n": len(closed),
        "expectancy_r": sum(num(row, "r_multiple") for row in closed) / len(closed),
        "win_rate": len(wins) / len(closed),
        "avg_win_r": (sum(num(row, "r_multiple") for row in wins) / len(wins)) if wins else None,
        "avg_loss_r": (sum(num(row, "r_multiple") for row in losses) / len(losses)) if losses else None,
        "median_stop_bps": statistics.median(stop_bps),
        "median_fee_r": statistics.median(fee_r),
    }


def main() -> None:
    runs = sorted((ROOT / "results" / "exp-s1-structure-v1").glob("*/trades.csv"))
    if not runs:
        raise SystemExit("No results/exp-s1-structure-v1/*/trades.csv found. Run from the repo root.")
    path = runs[-1]
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    exits = {}
    for row in rows:
        exits[row["exit_reason"]] = exits.get(row["exit_reason"], 0) + 1
    print(json.dumps({
        "file": str(path),
        "long": block([row for row in rows if row["side"] == "LONG"]),
        "short": block([row for row in rows if row["side"] == "SHORT"]),
        "exits": exits,
    }, indent=2))


if __name__ == "__main__":
    main()
