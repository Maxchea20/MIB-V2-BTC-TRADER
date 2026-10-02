"""Why the full Hunt loss runs happened."""

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = sorted((ROOT / "results" / "exp-hunt-desktop-cfi-v1").glob("*/trades.csv"))
    if not files:
        raise SystemExit("no full Hunt trades")
    trades = list(csv.DictReader(files[-1].open(encoding="utf-8")))
    runs = []
    start = None
    for i, trade in enumerate(trades):
        losing = float(trade["r_multiple"]) <= 0
        if losing and start is None:
            start = i
        if start is not None and (not losing or i == len(trades) - 1):
            end = i - 1 if not losing else i
            if end - start + 1 >= 5:
                runs.append(trades[start:end + 1])
            start = None
    print(json.dumps({"file": str(files[-1]), "runs": len(runs), "weather": _mix(runs, "weather"), "side": _mix(runs, "side"), "gate": _mix(runs, "gate"), "longest": _one(max(runs, key=len))}, indent=2))


def _mix(runs, key):
    counts = Counter(trade[key] for run in runs for trade in run)
    return dict(counts)


def _one(run):
    return {
        "n": len(run),
        "from": datetime.fromtimestamp(int(run[0]["entry_time"]) / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "to": datetime.fromtimestamp(int(run[-1]["entry_time"]) / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M"),
        "weather": dict(Counter(t["weather"] for t in run)),
        "side": dict(Counter(t["side"] for t in run)),
    }


if __name__ == "__main__":
    main()
