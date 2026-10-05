"""Execution audit: OLD backtest vs REALISTIC execution, on the same Hunt signals. Hunt V4 itself is not changed or tuned.
  OLD        the invalid fill at the level, idealised exits (exact stop/target price, no slippage, no latency)
  ENTRY ONLY real entry (market order after the closed 5m candle + latency), but still the idealised exits
  REALISTIC  the execution simulator for the entry AND every exit (gaps, slippage, trade-through, protective orders only after fill + latency)
Hunt V4 = Hunt V3 + Floors = Hunt (floors) outside the 1h box + the chop book, one position at a time. Both Hunt alone and V4 are shown.
Writes results\\execution_audit\\<file>\\ : report.txt, fires.csv (one row per FIRE, nothing silently dropped), trades_old.csv, trades_realistic.csv.
Usage: py scripts\\execution_audit.py research_binance [latency=1] [entry-slip=0.5] [exit-slip=0.5] [intrabar=conservative]
"""

import csv
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.execution.options import config_from_args

import backtest_desktop_cfi as eng
import backtest_hunt_chop as hc


def pf(rs):
    wins, losses = sum(r for r in rs if r > 0), -sum(r for r in rs if r < 0)
    return wins / losses if losses else float("inf")


def dip(rs):
    eq = peak = d = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        d = min(d, eq - peak)
    return d


def line(label, trades):
    rs = [float(t["r_multiple"]) for t in trades]
    if not rs:
        return f"  {label:<34} no trades"
    return f"  {label:<34} n={len(rs):5d}  avg {sum(rs) / len(rs):+.3f}R  total {sum(rs):+6.0f}R  win {sum(r > 0 for r in rs) / len(rs):3.0%}  PF(R) {pf(rs):.2f}  dip {dip(rs):7.1f}R"


def v4(hunt, series, active, keys, chop):
    kept = [dict(t, book="HUNT") for t in hunt if not hc._on(int(t["entry_time"]), active, keys, hc.HOUR)]
    return hc._one_position(kept, chop)


def run_all(bars, cfg):
    b5, b15, b1h, b4h = (resample(bars, x) for x in ("5m", "15m", "1h", "4h"))
    args = (bars, b5, b15, b1h, b4h, False, None, False, "floors")
    old = eng._run(*args, True)
    entry_only = eng._run(*args, False, cfg, None, True)
    events = []
    real = eng._run(*args, False, cfg, events)
    series = resample(bars, "1h")
    active = hc._flags(series)
    keys = sorted(active)
    hc.EXEC = None
    hc.REAL_STOP = False
    chop_old = hc._chop(series, active)
    hc.EXEC, hc.BARS_1M, hc.TIMES_1M = cfg, bars, [b.open_time for b in bars]
    chop_real = hc._chop(series, active)
    hc.EXEC = None
    return {"old": old, "entry_only": entry_only, "real": real, "events": events, "b5": b5,
            "v4_old": v4(old, series, active, keys, chop_old), "v4_real": v4(real, series, active, keys, chop_real),
            "chop_old": chop_old, "chop_real": chop_real}


def report(name, cfg, r):
    out = []
    p = out.append
    ev = r["events"]
    status = {}
    for e in ev:
        status[e["status"]] = status.get(e["status"], 0) + 1
    p(f"{name}: execution audit. latency {cfg.execution_latency_seconds}s, entry slip {cfg.slippage_ticks} tick + {cfg.entry_slippage_bps} bp, exit slip {cfg.slippage_ticks} tick + {cfg.exit_slippage_bps} bp, "
      f"fee {cfg.fee_bps_per_side} bp/side, TP needs {cfg.limit_trade_through_ticks} tick trade-through, same-bar stop+target: {cfg.intrabar_policy}")
    p("\nHUNT ALONE (floors), same signals, same strategy")
    p(line("OLD (fake fill, idealised exits)", r["old"]))
    p(line("ENTRY ONLY real, idealised exits", r["entry_only"]))
    p(line("REALISTIC execution", r["real"]))
    p("\nHUNT V4 (Hunt V3 + Floors)")
    p(line("OLD", r["v4_old"]))
    p(line("REALISTIC", r["v4_real"]))
    p(f"  chop book alone: old {len(r['chop_old'])} trades, realistic {len(r['chop_real'])} trades")

    old, real = r["old"], r["real"]
    sig = {e["signal_time"]: e for e in ev}
    by5 = {b.open_time: b for b in r["b5"]}
    real_by = {t["signal_time"]: t for t in real}
    old_by = {t["signal_time"]: t for t in old}
    matched = [k for k in old_by if k in real_by]
    old_only = [k for k in old_by if k not in real_by]
    new_only = [k for k in real_by if k not in old_by]
    imposs = mid = flips = 0
    for k in matched:
        o, n = old_by[k], real_by[k]
        sign = 1 if o["side"] == "LONG" else -1
        if (o["entry"] - n["entry_raw"]) * sign < 0:
            imposs += 1
        bar = by5.get(k - eng.FIVE)
        if bar and ((sign == 1 and o["entry"] < bar.low) or (sign == -1 and o["entry"] > bar.high)):
            mid += 1
        if (o["r_multiple"] > 0) != (n["r_multiple"] > 0):
            flips += 1
    why = {}
    for k in old_only:
        s = sig.get(k, {}).get("status", "NO_SIGNAL_IN_REALISTIC_RUN")
        why[s] = why.get(s, 0) + 1
    p("\nWHAT HAPPENED TO THE OLD TRADES (Hunt alone, matched by signal time)")
    p(f"  old trades {len(old)}  ->  realistic trades {len(real)}")
    p(f"  old trades whose entry price was BETTER than the first executable price after the signal (impossible fill): {imposs} of {len(matched)} matched ({imposs / max(1, len(matched)):.0%})")
    p(f"  old entry never traded inside the signal 5m candle (mid air): {mid} ({mid / max(1, len(matched)):.0%})")
    p(f"  old trades that DISAPPEAR (same signal does not become a trade): {len(old_only)} ({len(old_only) / max(1, len(old)):.0%})   reasons: {why or '-'}")
    p(f"  realistic trades that did not exist in the old run (different position timing): {len(new_only)}")
    p(f"  matched trades that flip between winner and loser: {flips}")

    filled = [t for t in real]
    p("\nEXECUTION STATISTICS (realistic run, Hunt alone)")
    valid = sum(status.get(s, 0) for s in ("ORDER_FILLED", "MISSED_FILL", "UNRESOLVED_BOTH_HIT"))
    p(f"  Hunt FIREs {len(ev)}  | skipped: position open {status.get('SKIPPED_POSITION_OPEN', 0)}, in the 15 min pause {status.get('SKIPPED_PAUSE', 0)}")
    p(f"  valid signals / orders submitted {valid}  | filled {status.get('ORDER_FILLED', 0)}  missed {status.get('MISSED_FILL', 0)}  unresolved same-bar {status.get('UNRESOLVED_BOTH_HIT', 0)}  | fill rate {status.get('ORDER_FILLED', 0) / max(1, valid):.1%}")
    if filled:
        es = [t["entry_slippage"] for t in filled]
        ebp = [t["entry_slippage"] / t["entry_raw"] * 1e4 for t in filled]
        xs = [t["exit_slippage"] for t in filled]
        xbp = [t["exit_slippage"] / t["exit_raw"] * 1e4 for t in filled]
        disp = [((t["entry"] - t["signal_price"]) * (1 if t["side"] == "LONG" else -1)) / t["signal_price"] * 1e4 for t in filled]
        p(f"  entry slippage: avg {statistics.mean(es):.2f} ({statistics.mean(ebp):.2f} bp), median {statistics.median(es):.2f} ({statistics.median(ebp):.2f} bp)")
        p(f"  entry displacement vs the signal candle close (+ = worse): avg {statistics.mean(disp):+.2f} bp, median {statistics.median(disp):+.2f} bp")
        p(f"  exit slippage: avg {statistics.mean(xs):.2f} ({statistics.mean(xbp):.2f} bp)   avg latency signal->fill {statistics.mean(t['latency_ms'] for t in filled) / 1000:.1f}s")
        gross = [t["gross_r_before_costs"] for t in filled]
        net = [t["r_multiple"] for t in filled]
        p(f"  PnL before execution costs {sum(gross):+.0f}R (avg {statistics.mean(gross):+.3f}R)   after slippage + fees {sum(net):+.0f}R (avg {statistics.mean(net):+.3f}R)")
        reasons = {}
        for t in filled:
            reasons[t["exit_reason"]] = reasons.get(t["exit_reason"], 0) + 1
        p(f"  exits: {reasons}")
    return "\n".join(out)


def main():
    cfg, rest = config_from_args(sys.argv[1:])
    name = rest[0] if rest else "research_binance"
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    r = run_all(bars, cfg)
    text = report(name, cfg, r)
    print(text)
    folder = ROOT / "results" / "execution_audit" / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "report.txt").write_text(text, encoding="utf-8")
    with (folder / "fires.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["signal_time", "signal_side", "signal_level", "signal_price", "event", "gate", "weather", "status", "reason"], extrasaction="ignore")
        w.writeheader()
        w.writerows(r["events"])
    for key, fname in (("old", "trades_old.csv"), ("real", "trades_realistic.csv")):
        with (folder / fname).open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, eng.FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(r[key])
    print(f"\nfiles: {folder}")


if __name__ == "__main__":
    main()
