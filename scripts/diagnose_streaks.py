"""Longest win and loss runs in the saved 4h stack trades."""

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
        out.append({"folder": str(folder), "combined": _streaks(rows), "long": _streaks([r for r in rows if r["side"] == "LONG"]), "short": _streaks([r for r in rows if r["side"] == "SHORT"])})
    print(json.dumps(out, indent=2))


def _streaks(rows):
    if not rows:
        return {"n": 0}
    wins = losses = max_wins = max_losses = 0
    win_runs = []
    loss_runs = []
    for row in rows:
        if float(row["net_pnl"]) > 0:
            if losses:
                loss_runs.append(losses)
                losses = 0
            wins += 1
            max_wins = max(max_wins, wins)
        else:
            if wins:
                win_runs.append(wins)
                wins = 0
            losses += 1
            max_losses = max(max_losses, losses)
    if wins:
        win_runs.append(wins)
    if losses:
        loss_runs.append(losses)
    return {
        "n": len(rows),
        "max_win_streak": max_wins,
        "max_loss_streak": max_losses,
        "loss_runs_of_5": sum(n >= 5 for n in loss_runs),
        "loss_runs_of_8": sum(n >= 8 for n in loss_runs),
        "win_runs_of_5": sum(n >= 5 for n in win_runs),
    }


if __name__ == "__main__":
    main()
