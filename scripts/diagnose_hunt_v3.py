"""Forensic split of the locked Hunt V3 book."""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOLE_START = int(datetime(2026, 7, 16, tzinfo=timezone.utc).timestamp() * 1000)
HOLE_END = int(datetime(2026, 8, 15, tzinfo=timezone.utc).timestamp() * 1000)


def main():
    files = sorted((ROOT / "results" / "exp-hunt-chop-arbiter").glob("*/trades.csv"))
    if not files:
        raise SystemExit("no Hunt V3 trades")
    rows = list(csv.DictReader(files[-1].open(encoding="utf-8")))
    hole = [r for r in rows if HOLE_START <= int(r["entry_time"]) < HOLE_END]
    print(json.dumps({
        "file": str(files[-1]),
        "combined": _bucket(rows),
        "by_book": {book: _bucket([r for r in rows if r["book"] == book]) for book in ("HUNT", "CHOP")},
        "by_side": {side: _bucket([r for r in rows if r["side"] == side]) for side in ("LONG", "SHORT")},
        "hole": _bucket(hole),
        "hole_by_book": {book: _bucket([r for r in hole if r["book"] == book]) for book in ("HUNT", "CHOP")},
        "months": _months(rows),
        "streaks": _streaks(rows),
    }, indent=2))


def _months(rows):
    out = {}
    for row in rows:
        key = datetime.fromtimestamp(int(row["entry_time"]) / 1000, timezone.utc).strftime("%Y-%m")
        out.setdefault(key, []).append(row)
    return {key: _bucket(out[key]) for key in sorted(out)}


def _streaks(rows):
    loss = win = max_loss = max_win = 0
    for row in rows:
        if float(row["r_multiple"]) > 0:
            win += 1
            loss = 0
        else:
            loss += 1
            win = 0
        max_loss = max(max_loss, loss)
        max_win = max(max_win, win)
    return {"max_win_streak": max_win, "max_loss_streak": max_loss}


def _bucket(rows):
    if not rows:
        return {"n": 0}
    equity = peak = dip = 0.0
    for row in rows:
        equity += float(row["r_multiple"])
        peak = max(peak, equity)
        dip = min(dip, equity - peak)
    return {
        "n": len(rows),
        "expectancy_r": round(sum(float(r["r_multiple"]) for r in rows) / len(rows), 4),
        "drawdown_r": round(dip, 2),
        "long": sum(r["side"] == "LONG" for r in rows),
        "short": sum(r["side"] == "SHORT" for r in rows),
        "stops": sum(r["exit_reason"] == "STOP" for r in rows),
        "targets": sum(r["exit_reason"] == "TARGET" for r in rows),
    }


if __name__ == "__main__":
    main()
