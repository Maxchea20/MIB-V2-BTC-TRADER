"""Build one HTML file: an interactive candle chart with every backtest trade drawn on it (entry, stop, target, exit).

Open the file in your browser (it needs no internet). Click a trade in the list, or a trade box on the chart. Times default to UTC+8.
Usage: py scripts\\build_viewer.py research_binance [source=base|floors|v4] [days5=120] [days15=730]
  source  base   = the Hunt trades from your Hunt run (default)
          floors = the newest floors Hunt file for this period (Hunt with Floors)
          v4     = Hunt V4: floors Hunt file + box switch (closed 1h bars) + chop book, one position. Takes a few minutes.
  days5   how many days of 5m candles to embed, counted back from the last trade (default 120)
  days15  how many days of 15m candles to embed (default 730). 1h candles always cover everything.
Writes results\\viewer\\<file>_<source>.html
"""

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

YEAR = {"research_2019_21": "2020", "research_2022_25": "2022", "research_binance": "2025"}
LABEL = {"base": "Hunt (stop 1R, target 1.67R)", "floors": "Hunt + Floors", "v4": "Hunt V4 (Hunt + Floors, box switch, chop book)"}


def candles(series, since=None):
    return [[b.open_time // 1000, round(b.open, 2), round(b.high, 2), round(b.low, 2), round(b.close, 2)] for b in series if since is None or b.open_time // 1000 >= since]


def _hunt_row(t, book="HUNT"):
    return {
        "a": int(t["entry_time"]) // 1000, "b": int(t["exit_time"]) // 1000, "s": 1 if t["side"] == "LONG" else -1,
        "e": round(float(t["entry"]), 2), "sl": round(float(t["stop"]), 2), "tp": round(float(t["target"]), 2), "x": round(float(t["exit"]), 2),
        "r": round(float(t["r_multiple"]), 3), "why": t["exit_reason"], "bk": book, "w": t.get("weather") or "", "g": (t.get("gate") or "") + (" " + t["event"] if t.get("event") else ""),
    }


def _chop_row(t):
    return {
        "a": int(t["entry_time"]) // 1000, "b": int(t["exit_time"]) // 1000 + 3600, "s": 1 if t["side"] == "LONG" else -1,
        "e": round(float(t["entry"]), 2), "sl": round(float(t["stop"]), 2), "tp": round(float(t["target"]), 2), "x": round(float(t["exit"]), 2),
        "r": round(float(t["r_multiple"]), 3), "why": t["exit_reason"], "bk": "CHOP", "w": "", "g": "box line",
    }


def _first_year(path):
    from datetime import datetime, timezone
    with path.open(encoding="utf-8") as handle:
        row = next(csv.DictReader(handle), None)
    return datetime.fromtimestamp(int(row["entry_time"]) / 1000, timezone.utc).strftime("%Y") if row else ""


def floors_file(name):
    folder = ROOT / "results" / "exp-hunt-desktop-cfi-floors"
    files = [f for f in sorted(folder.glob("*/trades.csv")) if _first_year(f) == YEAR[name]]
    if not files:
        raise SystemExit("no floors Hunt file for this period. Run: py scripts\\run_floor_v3.py " + name + " floors")
    return files[-1]


def base_file(name):
    text = (ROOT / "results" / "lock3" / f"{name}_hunt.txt").read_text(encoding="utf-8", errors="replace")
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    return file if file.is_absolute() else ROOT / file


def load_trades(name, source, series_1h):
    if source == "base":
        return [_hunt_row(t) for t in csv.DictReader(base_file(name).open(encoding="utf-8"))]
    hunt = list(csv.DictReader(floors_file(name).open(encoding="utf-8")))
    if source == "floors":
        return [_hunt_row(t) for t in hunt]
    import backtest_hunt_chop as hc
    active = hc._flags(series_1h)
    keys = sorted(active)
    kept = [t for t in hunt if not hc._on(int(t["entry_time"]), active, keys, hc.HOUR)]
    for t in kept:
        t["book"] = "HUNT"
    merged = hc._one_position(kept, hc._chop(series_1h, active))
    return [_hunt_row(t) if t["book"] == "HUNT" else _chop_row(t) for t in merged]


def build(name, source, bars, trades, days5=120, days15=730, tz=8, risk=50):
    from btc_research.data.resample import resample
    last = max(t["b"] for t in trades)
    s5, s15, s1h = resample(bars, "5m"), resample(bars, "15m"), resample(bars, "1h")
    c5, c15, c1h = candles(s5, last - days5 * 86400), candles(s15, last - days15 * 86400), candles(s1h)
    data = {
        "label": f"{name} - {LABEL[source]}", "tz": tz, "risk": risk,
        "cov": {k: [v[0][0], v[-1][0] + {"5m": 300, "15m": 900, "1h": 3600}[k]] for k, v in (("5m", c5), ("15m", c15), ("1h", c1h)) if v},
        "c": {"5m": c5, "15m": c15, "1h": c1h}, "tr": trades,
    }
    html = (ROOT / "viewer" / "template.html").read_text(encoding="utf-8")
    vendor = (ROOT / "viewer" / "vendor" / "lightweight-charts.standalone.production.js").read_text(encoding="utf-8")
    return html.replace("/*VENDOR*/", vendor.replace("</script>", "<\\/script>")).replace("/*DATA*/", json.dumps(data, separators=(",", ":")).replace("</", "<\\/"))


def main():
    name = sys.argv[1]
    opts = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)
    source = opts.get("source", "base")
    from btc_research.config import research_db_path
    from btc_research.data.loader import load_bars
    from btc_research.data.resample import resample
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    trades = load_trades(name, source, resample(bars, "1h") if source == "v4" else None)
    html = build(name, source, bars, trades, int(opts.get("days5", 120)), int(opts.get("days15", 730)))
    out = ROOT / "results" / "viewer"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}_{source}.html"
    path.write_text(html, encoding="utf-8")
    print(f"{name} ({source}): {len(trades)} trades, file {path.stat().st_size / 1e6:.1f} MB")
    print(f"  open this file in your browser: {path}")


if __name__ == "__main__":
    main()
