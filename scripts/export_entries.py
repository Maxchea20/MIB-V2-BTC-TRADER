"""Entry times to check on TradingView. Writes a CSV with every entry (UTC and UTC+8) and a Pine script that marks them on the chart.

What the times mean: the Hunt signal is a 5m candle that closes through the level. entry_time is the close of that 5m candle (= the open of the next one).
The entry price is the broken 15m level plus a small slippage, not the next candle's open. Check on a 5m chart; the signal candle is the 5m candle that ends at entry_time.
The data is Binance BTCUSDT, so use BINANCE:BTCUSDT.P (perpetual) on TradingView, with the chart timezone set to UTC to match the UTC column.

Usage: py scripts\\export_entries.py research_binance [from=2025-11-06] [to=2025-11-28] [max=150] [source=floors]
  from / to   keep entries in this UTC date range (default: all)
  max         how many entries go into the Pine script (the CSV has all; default 150, Pine allows 500 labels)
  source      base = the Hunt trades from your Hunt run (default). floors = the newest floors Hunt file for this period
Writes results\\tradingview\\<file>_entries.csv and <file>_entries.pine
"""

import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YEAR = {"research_2019_21": "2020", "research_2022_25": "2022", "research_binance": "2025"}
FIVE = 300_000


def _utc(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc)


def _fmt(ms, hours=0):
    return (_utc(ms) + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M")


def source_file(name, source):
    if source == "floors":
        folder = ROOT / "results" / "exp-hunt-desktop-cfi-floors"
        for f in reversed(sorted(folder.glob("*/trades.csv"))):
            with f.open(encoding="utf-8") as handle:
                row = next(csv.DictReader(handle), None)
            if row and _utc(int(row["entry_time"])).strftime("%Y") == YEAR[name]:
                return f
        raise SystemExit("no floors Hunt file for this period")
    text = (ROOT / "results" / "lock3" / f"{name}_hunt.txt").read_text(encoding="utf-8", errors="replace")
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    return file if file.is_absolute() else ROOT / file


def load(name, source="base", start=None, end=None):
    rows = []
    for t in csv.DictReader(source_file(name, source).open(encoding="utf-8")):
        ts = int(t["entry_time"])
        day = _utc(ts).strftime("%Y-%m-%d")
        if (start and day < start) or (end and day > end):
            continue
        rows.append({
            "entry_utc": _fmt(ts), "entry_utc8": _fmt(ts, 8), "signal_5m_candle_utc": f"{_fmt(ts - FIVE)} to {_fmt(ts)}",
            "side": t["side"], "entry_price": round(float(t["entry"]), 2), "stop": round(float(t["stop"]), 2), "target": round(float(t["target"]), 2),
            "event": t["event"], "gate": t["gate"], "weather": t["weather"], "exit_utc": _fmt(int(t["exit_time"])), "exit": t["exit_reason"],
            "R": round(float(t["r_multiple"]), 2), "_ts": ts, "_te": int(t["exit_time"]),
        })
    return rows


def pine(rows, limit):
    pick = rows[:limit]
    lines = [
        "//@version=5",
        f'indicator("Hunt entries ({len(pick)})", overlay=true, max_labels_count=500, max_lines_count=500)',
        "// Marks each Hunt entry: label = side, grey line = entry price, red = stop, green = target, drawn from entry to exit.",
        "var t0 = array.new_int()", "var t1 = array.new_int()", "var px = array.new_float()", "var sl = array.new_float()", "var tp = array.new_float()",
        "var sd = array.new_int()", "var rs = array.new_float()",
        "if barstate.isfirst",
    ]
    for r in pick:
        lines.append(f"    array.push(t0, {r['_ts']}), array.push(t1, {r['_te']}), array.push(px, {r['entry_price']}), array.push(sl, {r['stop']}), "
                     f"array.push(tp, {r['target']}), array.push(sd, {1 if r['side'] == 'LONG' else -1}), array.push(rs, {r['R']})")
    lines += [
        "if barstate.islast",
        "    for i = 0 to array.size(t0) - 1",
        "        long_ = array.get(sd, i) == 1",
        "        win = array.get(rs, i) > 0",
        '        txt = (long_ ? "L " : "S ") + str.tostring(array.get(rs, i), "#.##") + "R"',
        "        label.new(array.get(t0, i), array.get(px, i), txt, xloc=xloc.bar_time, style=long_ ? label.style_label_up : label.style_label_down, color=win ? color.green : color.red, textcolor=color.white, size=size.small)",
        "        line.new(array.get(t0, i), array.get(px, i), array.get(t1, i), array.get(px, i), xloc=xloc.bar_time, color=color.gray)",
        "        line.new(array.get(t0, i), array.get(sl, i), array.get(t1, i), array.get(sl, i), xloc=xloc.bar_time, color=color.red)",
        "        line.new(array.get(t0, i), array.get(tp, i), array.get(t1, i), array.get(tp, i), xloc=xloc.bar_time, color=color.green)",
    ]
    return "\n".join(lines) + "\n"


def main():
    name = sys.argv[1]
    opts = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)
    rows = load(name, opts.get("source", "base"), opts.get("from"), opts.get("to"))
    out = ROOT / "results" / "tradingview"
    out.mkdir(parents=True, exist_ok=True)
    cols = [c for c in rows[0] if not c.startswith("_")]
    with (out / f"{name}_entries.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    limit = int(opts.get("max", 150))
    (out / f"{name}_entries.pine").write_text(pine(rows, limit), encoding="utf-8")
    print(f"{name}: {len(rows)} entries in the CSV, {min(limit, len(rows))} in the Pine script")
    print(f"  {out / (name + '_entries.csv')}")
    print(f"  {out / (name + '_entries.pine')}")
    print("  first five entries (UTC, UTC+8, side, entry price, outcome):")
    for r in rows[:5]:
        print(f"    {r['entry_utc']}  {r['entry_utc8']}  {r['side']:<5} {r['entry_price']}  {r['exit']} {r['R']:+}R")


if __name__ == "__main__":
    main()
