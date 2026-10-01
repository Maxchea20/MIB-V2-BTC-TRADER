"""Did a closed trade go the right way first, or the wrong way first?"""

import csv
import json
import sys
from pathlib import Path


def num(row, key):
    return float(row[key])


def bucket(rows):
    closed = [r for r in rows if r["exit_reason"] != "END_OF_DATA"]
    targets = [r for r in closed if r["exit_reason"] == "TARGET"]
    stops = [r for r in closed if r["exit_reason"].startswith("STOP")]
    return {
        "n": len(closed),
        "target_straight": sum(num(r, "mae_r") < 0.25 for r in targets),
        "target_after_going_against": sum(num(r, "mae_r") >= 0.5 for r in targets),
        "stop_straight": sum(num(r, "mfe_r") < 0.25 for r in stops),
        "stop_after_going_in_favor": sum(num(r, "mfe_r") >= 0.5 for r in stops),
    }


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "exp-hunt-lookback-20-target-1r"
    folders = sorted(p for p in Path("results", name).glob("*") if (p / "trades.csv").exists())
    if not folders:
        raise SystemExit(f"no trades in results/{name}")
    rows = list(csv.DictReader((folders[-1] / "trades.csv").open(encoding="utf-8")))
    out = {"file": str(folders[-1] / "trades.csv"), "combined": bucket(rows)}
    out["long"] = bucket([r for r in rows if r["side"] == "LONG"])
    out["short"] = bucket([r for r in rows if r["side"] == "SHORT"])
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
