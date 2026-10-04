"""Full report for three Hunt exits side by side: profit factor, PnL in dollars, average win and loss, streaks, months, exit mix.

Plain Hunt entries (no box, no chop book), same entries for every column. R = today's stop distance; every trade risks the same dollars.
  today      SL 1R : TP 1.67R
  V4 exit    SL 1R : TP 1.67R + floors   (the exit inside Hunt V4)
  2.5R       SL 1R : TP 2.5R + floors    (the best candidate so far)
Dollar lines assume you risk $RISK on every trade (default 50): py scripts\\report_hunt_variant.py research_binance 50
"""

import csv
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.setups import hunt_exits

U = 1.5
FUNDING = 0.000026  # +0.0026% per 8 hours, from the exchange screen
COLUMNS = (("today", 1.0, 5 / 3, False), ("V4 exit", 1.0, 5 / 3, True), ("2.5R + floors", 1.0, 2.5, True))


def floors_cfg(tp_r):
    tp = tp_r * U
    return dict(tiers=((0.7 * tp, 0.6 * tp), (0.9 * tp, 0.8 * tp)))


def run(bars, trades, sl_r, tp_r, floors):
    cfg = floors_cfg(tp_r) if floors else dict(tiers=())
    out = []
    for t in trades:
        entry, stop = float(t["entry"]), float(t["stop"])
        risk0 = abs(entry - stop)
        sign = 1 if t["side"] == "LONG" else -1
        trade = {"side": t["side"], "entry": entry, "stop": entry - sign * sl_r * risk0, "target": entry + sign * tp_r * risk0,
                 "atr": risk0 / U, "risk": sl_r * risk0}
        done = hunt_exits.walk(trade, bars, int(t["entry_time"]), bars[-1].open_time + 60_000, cfg)
        if done is None:
            done = hunt_exits._close(trade, bars[-1].close, bars[-1].open_time, "END")
        fee_r = (entry + done["exit"]) * 0.0002 / done["risk"]
        out.append({"r": done["r_multiple"], "reason": done["exit_reason"], "t0": int(t["entry_time"]), "t1": done["exit_time"], "fee_r": fee_r,
                    "side": t["side"], "risk_pct": done["risk"] / entry})
    return out


def summarize(rows, risk):
    rs = [x["r"] for x in rows]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    eq = peak = dip = 0.0
    peak_t = rows[0]["t0"]
    under, worst_under = None, 0
    streak = longest = 0
    for x in sorted(rows, key=lambda x: x["t1"]):
        eq += x["r"]
        if eq >= peak:
            if under is not None:
                worst_under = max(worst_under, x["t1"] - under)
                under = None
            peak, peak_t = eq, x["t1"]
        else:
            under = under if under is not None else peak_t
            dip = min(dip, eq - peak)
        streak = streak + 1 if x["r"] <= 0 else 0
        longest = max(longest, streak)
    if under is not None:
        worst_under = max(worst_under, rows[-1]["t1"] - under)
    days = (max(x["t1"] for x in rows) - min(x["t0"] for x in rows)) / 86_400_000
    months = {}
    for x in rows:
        months.setdefault(datetime.fromtimestamp(x["t1"] / 1000, timezone.utc).strftime("%Y-%m"), 0.0)
        months[datetime.fromtimestamp(x["t1"] / 1000, timezone.utc).strftime("%Y-%m")] += x["r"]
    total = sum(rs)
    mix = {k: sum(x["reason"] == k for x in rows) for k in ("TARGET", "FLOOR", "STOP", "END")}
    return [
        ("trades", f"{len(rs)}"),
        ("trades per day", f"{len(rs) / days:.1f}"),
        ("win rate", f"{len(wins) / len(rs):.0%}"),
        ("average win", f"{sum(wins) / len(wins):+.2f}R  (${sum(wins) / len(wins) * risk:,.0f})"),
        ("average loss", f"{sum(losses) / len(losses):+.2f}R  (${sum(losses) / len(losses) * risk:,.0f})"),
        ("profit factor", f"{sum(wins) / abs(sum(losses)):.2f}"),
        ("average per trade", f"{total / len(rs):+.3f}R  (${total / len(rs) * risk:,.2f})"),
        ("median trade", f"{statistics.median(rs):+.2f}R"),
        ("total", f"{total:+.0f}R  (${total * risk:,.0f})"),
        ("per month", f"{total / (days / 30.4):+.1f}R  (${total / (days / 30.4) * risk:,.0f})"),
        ("per year", f"{total / (days / 365):+.0f}R  (${total / (days / 365) * risk:,.0f})"),
        ("best / worst trade", f"{max(rs):+.1f}R / {min(rs):+.1f}R"),
        ("worst drawdown", f"{dip:.1f}R  (${dip * risk:,.0f})"),
        ("longest time under a peak", f"{worst_under / 86_400_000:.0f} days"),
        ("longest losing streak", f"{longest} trades"),
        ("profitable months", f"{sum(v > 0 for v in months.values())} of {len(months)}  (worst {min(months.values()):+.0f}R, best {max(months.values()):+.0f}R)"),
        ("avg per trade if fee is", " / ".join(f"{(total + sum(x['fee_r'] for x in rows) * (1 - bp / 2)) / len(rs):+.3f}R at {bp:g}bp" for bp in (0, 1, 3, 4))),
        ("avg if TP exits are maker 0%", f"{(total + sum(x['fee_r'] / 2 for x in rows if x['reason'] == 'TARGET')) / len(rs):+.3f}R  (limit order at the target; entry and stops stay taker 0.02%)"),
        ("funding effect", f"{-sum(FUNDING * ((x['t1'] - x['t0']) / 3_600_000 / 8) / x['risk_pct'] * (1 if x['side'] == 'LONG' else -1) for x in rows) / len(rs):+.4f}R per trade  (+0.0026% per 8h, longs pay, shorts receive)"),
        ("fees paid", f"{sum(x['fee_r'] for x in rows):.0f}R  ({sum(x['fee_r'] for x in rows) / len(rs):.3f}R per trade)"),
        ("exits: TP / floor / stop", f"{mix['TARGET']} / {mix['FLOOR']} / {mix['STOP']}" + (f" (+{mix['END']} open at the end)" if mix["END"] else "")),
    ]


def main():
    name = sys.argv[1]
    risk = float(sys.argv[2]) if len(sys.argv) > 2 else 50.0
    text = (ROOT / "results" / "lock3" / f"{name}_hunt.txt").read_text(encoding="utf-8", errors="replace")
    file = Path(json.loads(text[text.index("{"):text.rindex("}") + 1])["file"])
    if not file.is_absolute():
        file = ROOT / file
    trades = list(csv.DictReader(file.open(encoding="utf-8")))
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    tables = [summarize(run(bars, trades, sl, tp, fl), risk) for _, sl, tp, fl in COLUMNS]
    print(f"{name}: Hunt entries, risk ${risk:g} per trade. Same entries in every column")
    print(f"  {'':<27}" + "".join(f"{label:<44}" for label, *_ in COLUMNS))
    for i in range(len(tables[0])):
        print(f"  {tables[0][i][0]:<27}" + "".join(f"{t[i][1]:<44}" for t in tables))


if __name__ == "__main__":
    main()
