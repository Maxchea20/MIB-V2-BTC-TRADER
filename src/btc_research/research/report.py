"""Result writers. Compact files only. No candle dumps."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def write_run(out_dir: Path, config: dict, trades: list, skips: dict, meta: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = build_summary(trades, skips, meta)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "experiment_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (out_dir / "failure_analysis.json").write_text(json.dumps({"skip_counts": skips, "exit_reasons": _counts(trades, "exit_reason"), "notes": summary["notes"]}, indent=2), encoding="utf-8")
    _csv(out_dir / "trades.csv", trades)
    _csv(out_dir / "equity_curve.csv", _equity(trades))
    _csv(out_dir / "daily_stats.csv", _daily(trades))
    _csv(out_dir / "setup_stats.csv", [_stats_row("S1", trades)])
    rows = [_stats_row(side, [t for t in trades if t["side"] == side]) for side in ("LONG", "SHORT")]
    rows.append(_stats_row("COMBINED", trades))
    _csv(out_dir / "long_short_stats.csv", rows)
    print(f"wrote {out_dir}")
    print(json.dumps({k: summary[k] for k in ("trades", "net_expectancy_r", "profit_factor", "win_rate", "max_drawdown_r")}, indent=2))


def build_summary(trades, skips, meta):
    closed = [t for t in trades if t["exit_reason"] != "END_OF_DATA"]
    notes = [
        "HYPOTHESIS result only. Do not treat a positive number as a live edge.",
        "Funding is 0 until a funding table is present. Status is MISSING_NOT_APPLIED.",
        "Same-bar stop and target fills the stop.",
        "A huge EXTENSION skip count means the 1.5 ATR cap is tight, not that the loader failed.",
    ]
    combined = _block(closed)
    return {**meta, "trades": len(closed), "open_at_end": len(trades) - len(closed), "skip_counts": skips, "combined": combined, "long": _block([t for t in closed if t["side"] == "LONG"]), "short": _block([t for t in closed if t["side"] == "SHORT"]), "net_expectancy_r": combined["expectancy_r"], "profit_factor": combined["profit_factor"], "win_rate": combined["win_rate"], "max_drawdown_r": combined["max_drawdown_r"], "notes": notes}


def _block(trades):
    if not trades:
        return {"trades": 0, "expectancy_r": None, "profit_factor": None, "win_rate": None, "max_drawdown_r": None}
    rs = [t["r_multiple"] for t in trades]
    wins = [t for t in trades if t["net_pnl"] > 0]
    losses = [t for t in trades if t["net_pnl"] <= 0]
    gross_win = sum(t["net_pnl"] for t in wins)
    gross_loss = abs(sum(t["net_pnl"] for t in losses))
    peak = equity = 0.0
    max_dd = 0.0
    streak = max_streak = 0
    for r in rs:
        equity += r
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
        streak = streak + 1 if r <= 0 else 0
        max_streak = max(max_streak, streak)
    return {"trades": len(trades), "gross_pnl": sum(t["gross_pnl"] for t in trades), "fees": sum(t["fees"] for t in trades), "funding": sum(t["funding_pnl"] for t in trades), "net_pnl": sum(t["net_pnl"] for t in trades), "net_r": sum(rs), "expectancy_r": sum(rs) / len(rs), "profit_factor": (gross_win / gross_loss) if gross_loss else None, "win_rate": len(wins) / len(trades), "average_win": (sum(t["net_pnl"] for t in wins) / len(wins)) if wins else 0, "average_loss": (sum(t["net_pnl"] for t in losses) / len(losses)) if losses else 0, "max_drawdown_r": max_dd, "max_consecutive_losses": max_streak, "average_mfe_r": sum(t["mfe_r"] for t in trades) / len(trades), "average_mae_r": sum(t["mae_r"] for t in trades) / len(trades), "average_hold_seconds": sum(t["hold_seconds"] for t in trades) / len(trades)}


def _equity(trades):
    equity = 0.0
    rows = []
    for t in trades:
        equity += t["r_multiple"]
        rows.append({"exit_time": t["exit_time"], "side": t["side"], "r": t["r_multiple"], "equity_r": equity})
    return rows


def _daily(trades):
    buckets = defaultdict(list)
    for t in trades:
        day = datetime.fromtimestamp(t["exit_time"] / 1000, tz=timezone.utc).date().isoformat()
        buckets[day].append(t)
    return [{"date": day, "trades": len(rows), "net_r": sum(t["r_multiple"] for t in rows)} for day, rows in sorted(buckets.items())]


def _stats_row(label, trades):
    block = _block([t for t in trades if t.get("exit_reason") != "END_OF_DATA"])
    block["label"] = label
    return block


def _counts(trades, key):
    out = {}
    for t in trades:
        out[t[key]] = out.get(t[key], 0) + 1
    return out


def _csv(path: Path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
