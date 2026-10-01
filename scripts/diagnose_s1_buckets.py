"""Split the latest S1 trades by stop width. No new backtest."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINS = (20, 30, 40, 60, 80)


def main() -> None:
    runs = sorted((ROOT / "results" / "exp-s1-structure-v1").glob("*/trades.csv"))
    if not runs:
        raise SystemExit("No S1 trades.csv found. Run from the repo root.")
    with runs[-1].open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    out = []
    for side in ("LONG", "SHORT"):
        chosen = [row for row in rows if row["side"] == side and row["exit_reason"] != "END_OF_DATA"]
        for low, high in zip((0, *BINS), (*BINS, 10_000)):
            bucket = []
            for row in chosen:
                stop_bps = abs(float(row["entry"]) - float(row["stop"])) / float(row["entry"]) * 10_000
                if low <= stop_bps < high:
                    bucket.append(float(row["r_multiple"]))
            out.append({
                "side": side,
                "stop_bps": f"{low}-{high}",
                "n": len(bucket),
                "expectancy_r": (sum(bucket) / len(bucket)) if bucket else None,
                "win_rate": (sum(value > 0 for value in bucket) / len(bucket)) if bucket else None,
            })
    print(json.dumps({"file": str(runs[-1]), "buckets": out}, indent=2))


if __name__ == "__main__":
    main()
