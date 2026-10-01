"""Rescore an existing experiment at another taker fee. No candle replay."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    experiment = sys.argv[1] if len(sys.argv) > 1 else "exp-s2-structure-v1"
    bps = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    recorded = 4.0
    runs = sorted((ROOT / "results" / experiment).glob("*/trades.csv"))
    if not runs:
        raise SystemExit(f"No results/{experiment}/*/trades.csv found. Run from the repo root.")
    with runs[-1].open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    scale = bps / recorded
    out = {}
    for side in ("LONG", "SHORT", "COMBINED"):
        chosen = rows if side == "COMBINED" else [row for row in rows if row["side"] == side]
        values = []
        for row in chosen:
            if row["exit_reason"] == "END_OF_DATA":
                continue
            risk = abs(float(row["entry"]) - float(row["stop"]))
            net = float(row["gross_pnl"]) - float(row["fees"]) * scale
            values.append(net / risk if risk else 0.0)
        out[side] = {
            "n": len(values),
            "expectancy_r": (sum(values) / len(values)) if values else None,
            "win_rate": (sum(value > 0 for value in values) / len(values)) if values else None,
        }
    print(json.dumps({"file": str(runs[-1]), "taker_bps_per_side": bps, "sides": out}, indent=2))


if __name__ == "__main__":
    main()
