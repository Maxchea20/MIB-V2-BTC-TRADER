"""After 3 losses, drop the next saved trade. This does not invent a replacement trade."""

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
        out.append({"folder": str(folder), "baseline": _score(rows), "skip_any_side": _score(_skip(rows, False)), "skip_same_side": _score(_skip(rows, True))})
    print(json.dumps(out, indent=2))


def _skip(rows, same_side):
    kept = []
    losses = 0
    skip_side = None
    for row in rows:
        if skip_side and (not same_side or row["side"] == skip_side):
            skip_side = None
            losses = 0
            continue
        kept.append(row)
        if float(row["net_pnl"]) <= 0:
            losses += 1
            if losses >= 3:
                skip_side = row["side"]
                losses = 0
        else:
            losses = 0
            skip_side = None
    return kept


def _score(rows):
    if not rows:
        return {"n": 0}
    wins = [r for r in rows if float(r["net_pnl"]) > 0]
    losses = [r for r in rows if float(r["net_pnl"]) <= 0]
    gross_loss = abs(sum(float(r["net_pnl"]) for r in losses))
    streak = max_streak = 0
    for row in rows:
        if float(row["net_pnl"]) <= 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return {
        "n": len(rows),
        "expectancy_r": round(sum(float(r["r_multiple"]) for r in rows) / len(rows), 4),
        "profit_factor": round(sum(float(r["net_pnl"]) for r in wins) / gross_loss, 4) if gross_loss else None,
        "max_loss_streak": max_streak,
    }


if __name__ == "__main__":
    main()
