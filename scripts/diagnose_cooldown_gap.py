"""Hours from a losing exit to the next entry. A cooldown only bites inside that gap."""

import csv
import json
from pathlib import Path


def main():
    folders = sorted(p for p in Path("results", "exp-mtf-4h-1h-15m-v1").glob("*") if (p / "trades.csv").exists())
    if not folders:
        raise SystemExit("no trades")
    out = []
    for folder in folders:
        rows = [r for r in csv.DictReader((folder / "trades.csv").open(encoding="utf-8")) if r["exit_reason"] != "END_OF_DATA"]
        gaps = []
        for prev, nxt in zip(rows, rows[1:]):
            if float(prev["net_pnl"]) > 0:
                continue
            gap = (float(nxt["entry_time"]) - float(prev["exit_time"])) / 3_600_000
            gaps.append(gap)
        out.append({"folder": str(folder), "after_loss": _pack(gaps), "inside_loss_run": _pack(_run_gaps(rows))})
    print(json.dumps(out, indent=2))


def _run_gaps(rows):
    gaps = []
    current = []
    for row in rows:
        if float(row["net_pnl"]) <= 0:
            current.append(row)
            continue
        gaps.extend(_inside(current))
        current = []
    gaps.extend(_inside(current))
    return gaps


def _inside(rows):
    if len(rows) < 2:
        return []
    return [(float(b["entry_time"]) - float(a["exit_time"])) / 3_600_000 for a, b in zip(rows, rows[1:])]


def _pack(gaps):
    if not gaps:
        return {"n": 0}
    ordered = sorted(gaps)
    return {
        "n": len(gaps),
        "median_hours": round(ordered[len(ordered) // 2], 2),
        "within_2h": round(sum(g <= 2 for g in gaps) / len(gaps), 3),
        "within_6h": round(sum(g <= 6 for g in gaps) / len(gaps), 3),
        "over_6h": round(sum(g > 6 for g in gaps) / len(gaps), 3),
    }


if __name__ == "__main__":
    main()
