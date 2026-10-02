"""Win and loss streaks for the two locked books."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    folders = [
        ROOT / "results" / "exp-mtf-4h-1h-15m-v1",
        ROOT / "results" / "exp-hunt-desktop-cfi-v1",
    ]
    for folder in folders:
        files = sorted(folder.glob("*/trades.csv"))
        if not files:
            continue
        trades = list(csv.DictReader(files[-1].open(encoding="utf-8")))
        print(json.dumps({"file": str(files[-1]), "combined": _streak(trades), "long": _streak([t for t in trades if t["side"] == "LONG"]), "short": _streak([t for t in trades if t["side"] == "SHORT"])}, indent=2))


def _streak(trades):
    win = loss = max_win = max_loss = 0
    loss5 = loss8 = win5 = 0
    for trade in trades:
        if float(trade["r_multiple"]) > 0:
            if loss:
                loss5 += loss >= 5
                loss8 += loss >= 8
            loss = 0
            win += 1
            max_win = max(max_win, win)
        else:
            if win:
                win5 += win >= 5
            win = 0
            loss += 1
            max_loss = max(max_loss, loss)
    loss5 += loss >= 5
    loss8 += loss >= 8
    win5 += win >= 5
    return {"n": len(trades), "max_win_streak": max_win, "max_loss_streak": max_loss, "loss_runs_of_5": loss5, "loss_runs_of_8": loss8, "win_runs_of_5": win5}


if __name__ == "__main__":
    main()
