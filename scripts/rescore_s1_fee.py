"""Rescore the latest S1 trades at another taker fee. No candle replay."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    bps = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    runs = sorted((ROOT / "results" / "exp-s1-structure-v1").glob("*/trades.csv"))
    if not runs:
        raise SystemExit("No S1 trades.csv found. Run from the repo root.")
    with runs[-1].open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    scale = bps / 4.0
    out = {}
    for side in ("LONG", "SHORT", "COMBINED"):
        chosen = rows if side == "COMBINED" else [row for row in rows if row["side"] == side]
        rs = []
        for row in chosen:
            if row["exit_reason"] == "END_OF_DATA":
                continue
            risk = abs(float(row["entry"]) - float(row["stop"]))
            fee = float(row["fees"]) * scale
            net = float(row["gross_pnl"]) - fee
            rs.append(net / risk if risk else 0.0)
        out[side] = {
            "n": len(rs),
            "expectancy_r": (sum(rs) / len(rs)) if rs else None,
            "win_rate": (sum(value > 0 for value in rs) / len(rs)) if rs else None,
        }
    print(json.dumps({"file": str(runs[-1]), "taker_bps_per_side": bps, "note": "Entry was a next-open fill, so taker is the matching assumption. Maker 0% is not applied.", "sides": out}, indent=2))


if __name__ == "__main__":
    main()
