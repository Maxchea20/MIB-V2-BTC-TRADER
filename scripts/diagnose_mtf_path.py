"""Did the 4h stack go the right way first? All saved runs."""

import csv
import json
from pathlib import Path


def main():
    folders = sorted(p for p in Path("results", "exp-mtf-4h-1h-15m-v1").glob("*") if (p / "trades.csv").exists())
    if not folders:
        raise SystemExit("no trades")
    out = []
    for folder in folders:
        rows = list(csv.DictReader((folder / "trades.csv").open(encoding="utf-8")))
        out.append({"folder": str(folder), "combined": _bucket(rows), "long": _bucket([r for r in rows if r["side"] == "LONG"]), "short": _bucket([r for r in rows if r["side"] == "SHORT"])})
    print(json.dumps(out, indent=2))


def _bucket(rows):
    closed = [r for r in rows if r["exit_reason"] != "END_OF_DATA"]
    targets = [r for r in closed if r["exit_reason"] == "TARGET"]
    stops = [r for r in closed if r["exit_reason"].startswith("STOP")]
    mfe = sorted(float(r["mfe_r"]) for r in closed)
    mae = sorted(float(r["mae_r"]) for r in closed)
    return {
        "n": len(closed),
        "median_mfe_r": round(mfe[len(mfe) // 2], 3) if mfe else None,
        "median_mae_r": round(mae[len(mae) // 2], 3) if mae else None,
        "target_straight": sum(float(r["mae_r"]) < 0.25 for r in targets),
        "target_after_going_against": sum(float(r["mae_r"]) >= 0.5 for r in targets),
        "stop_straight": sum(float(r["mfe_r"]) < 0.25 for r in stops),
        "stop_after_going_in_favor": sum(float(r["mfe_r"]) >= 0.5 for r in stops),
    }


if __name__ == "__main__":
    main()
