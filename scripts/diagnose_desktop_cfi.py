"""Read the latest desktop Hunt trade file and show where the loss sits."""

import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results" / "exp-hunt-desktop-cfi-v1"
    files = sorted(folder.glob("*/trades.csv")) if folder.is_dir() else [folder]
    if not files:
        raise SystemExit("no trades.csv")
    path = files[-1]
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    for row in rows:
        row["r"] = float(row["r_multiple"])
        row["hold_min"] = (int(row["exit_time"]) - int(row["entry_time"])) / 60_000
        row["stop_bps"] = abs(float(row["entry"]) - float(row["stop"])) / float(row["entry"]) * 10_000
    print(json.dumps({
        "file": str(path),
        "combined": _bucket(rows),
        "by_gate": {k: _bucket([r for r in rows if r["gate"] == k]) for k in ("cfast", "internal", "rearm")},
        "by_side": {k: _bucket([r for r in rows if r["side"] == k]) for k in ("LONG", "SHORT")},
        "by_weather": {k: _bucket([r for r in rows if r["weather"] == k]) for k in ("SWING_UP", "SWING_DOWN", "CHOP")},
        "by_event": {k: _bucket([r for r in rows if r["event"] == k]) for k in ("BOS", "CHoCH")},
        "same_bar_stop": _bucket([r for r in rows if r["exit_reason"] == "STOP" and r["hold_min"] <= 5]),
        "stop_under_30bps": _bucket([r for r in rows if r["stop_bps"] < 30]),
    }, indent=2))


def _bucket(rows):
    if not rows:
        return {"n": 0}
    wins = [r for r in rows if r["r"] > 0]
    losses = [r for r in rows if r["r"] <= 0]
    gross_loss = abs(sum(float(r["net_pnl"]) for r in losses))
    return {
        "n": len(rows),
        "expectancy_r": round(sum(r["r"] for r in rows) / len(rows), 4),
        "profit_factor": round(sum(float(r["net_pnl"]) for r in wins) / gross_loss, 4) if gross_loss else None,
        "stops": sum(r["exit_reason"] == "STOP" for r in rows),
        "targets": sum(r["exit_reason"] == "TARGET" for r in rows),
        "median_hold_min": round(statistics.median(r["hold_min"] for r in rows), 1),
        "median_stop_bps": round(statistics.median(r["stop_bps"] for r in rows), 1),
    }


if __name__ == "__main__":
    main()
