"""What the losing runs of 5 or more looked like. No new trades."""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def main():
    folders = sorted(p for p in Path("results", "exp-mtf-4h-1h-15m-v1").glob("*") if (p / "trades.csv").exists())
    if not folders:
        raise SystemExit("no trades")
    out = []
    for folder in folders:
        rows = [r for r in csv.DictReader((folder / "trades.csv").open(encoding="utf-8")) if r["exit_reason"] != "END_OF_DATA"]
        runs = _runs(rows)
        out.append({"folder": str(folder), "loss_runs_of_5": len(runs), "runs": runs})
    print(json.dumps(out, indent=2))


def _runs(rows):
    found = []
    current = []
    for row in rows:
        if float(row["net_pnl"]) <= 0:
            current.append(row)
            continue
        if len(current) >= 5:
            found.append(_pack(current))
        current = []
    if len(current) >= 5:
        found.append(_pack(current))
    return found


def _pack(rows):
    start = int(float(rows[0].get("entry_time") or rows[0].get("decision_time") or 0))
    end = int(float(rows[-1].get("exit_time") or 0))
    return {
        "n": len(rows),
        "r": round(sum(float(r["r_multiple"]) for r in rows), 2),
        "long": sum(r["side"] == "LONG" for r in rows),
        "short": sum(r["side"] == "SHORT" for r in rows),
        "went_in_favor_first": sum(float(r["mfe_r"]) >= 0.5 for r in rows),
        "straight_stop": sum(float(r["mfe_r"]) < 0.25 for r in rows),
        "start": datetime.fromtimestamp(start / 1000, tz=timezone.utc).strftime("%Y-%m-%d") if start else None,
        "hours": round(max(0, end - start) / 3_600_000, 1) if start and end else None,
    }


if __name__ == "__main__":
    main()
