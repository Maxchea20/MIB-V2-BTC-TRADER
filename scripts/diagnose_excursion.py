"""Measure post-entry excursion. No candle replay."""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    out = []
    for experiment in ("exp-s1-structure-v1", "exp-s2-structure-v1", "exp-s3-structure-v1", "exp-s4-structure-v1"):
        runs = sorted((ROOT / "results" / experiment).glob("*/trades.csv"))
        if not runs:
            continue
        with runs[-1].open(encoding="utf-8") as handle:
            rows = [row for row in csv.DictReader(handle) if row["exit_reason"] != "END_OF_DATA"]
        mfe = [float(row["mfe_r"]) for row in rows]
        mae = [float(row["mae_r"]) for row in rows]
        out.append({
            "experiment": experiment,
            "n": len(rows),
            "median_mfe_r": statistics.median(mfe) if mfe else None,
            "median_mae_r": statistics.median(mae) if mae else None,
            "share_mfe_below_0.5r": (sum(value < 0.5 for value in mfe) / len(mfe)) if mfe else None,
            "share_stopped_or_worse": (sum(value <= -1 for value in mae) / len(mae)) if mae else None,
        })
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
