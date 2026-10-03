"""Which Hunt V3 Hunt trades do better? Avg R by feature, three files side by side. No new backtest.

Only a bucket that has the same sign on all three files is worth a second look (marked + or -).
Usage: py scripts\\diagnose_hunt_features.py research_2019_21 research_2022_25 research_binance
"""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _json(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


def _read(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    return list(csv.DictReader(path.open(encoding="utf-8")))


def _load(name):
    res = _json(ROOT / "results" / "lock3" / f"{name}_switch.txt")
    features = {r["entry_time"]: r for r in _read(res["hunt_file"])}
    rows = []
    for t in _read(res["file"]):
        src = features.get(t["entry_time"])
        if t["book"] != "HUNT" or not src:
            continue
        when = datetime.fromtimestamp(int(t["entry_time"]) / 1000, timezone.utc)
        rows.append({
            "r": float(t["r_multiple"]), "win": t["exit_reason"] == "TARGET",
            "event": src["event"], "gate": src["gate"], "weather": src["weather"], "side": t["side"],
            "hour": f"{when.hour // 4 * 4:02d}-{when.hour // 4 * 4 + 4:02d}h", "day": when.strftime("%a"),
            "risk": abs(float(src["entry"]) - float(src["stop"])) / float(src["entry"]),
        })
    cuts = sorted(r["risk"] for r in rows)
    lo, hi = cuts[len(cuts) // 3], cuts[2 * len(cuts) // 3]
    for r in rows:
        r["vol"] = "1 low" if r["risk"] < lo else ("3 high" if r["risk"] >= hi else "2 mid")
    return rows


def main():
    names = sys.argv[1:]
    data = {n: _load(n) for n in names}
    means = {n: sum(r["r"] for r in rows) / len(rows) for n, rows in data.items()}
    print("Hunt V3 Hunt trades, avg R and trade count by feature")
    print("  " + "all".ljust(18) + "".join(f"{n[-8:]:>18}" for n in names))
    print("  " + "".ljust(18) + "".join(f"{len(data[n]):>7} {means[n]:+.3f}R   " for n in names))
    for feature in ("event", "gate", "weather", "side", "vol", "hour", "day"):
        print(f"  [{feature}]")
        buckets = sorted({r[feature] for rows in data.values() for r in rows})
        for b in buckets:
            cells, signs = [], []
            for n in names:
                sub = [r for r in data[n] if r[feature] == b]
                if len(sub) < 30:
                    cells.append(f"{len(sub):>7}    n/a   ")
                    signs.append(0)
                    continue
                avg = sum(r["r"] for r in sub) / len(sub)
                cells.append(f"{len(sub):>7} {avg:+.3f}R   ")
                signs.append(1 if avg > means[n] + 0.05 else (-1 if avg < means[n] - 0.05 else 0))
            mark = "+" if all(s == 1 for s in signs) else ("-" if all(s == -1 for s in signs) else " ")
            print(f"  {mark} {b:<16}" + "".join(cells))


if __name__ == "__main__":
    main()
