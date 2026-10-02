"""Same 4h stack. Lookback 10, 12, 14, 16, 18, 20 on every clock."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import experiment_config, research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.setups.mtf_stack import run_mtf


def main():
    paths = sys.argv[1:] or [None]
    cfg = experiment_config("exp-mtf-4h-1h-15m-v1")
    rows = []
    for raw in paths:
        db = research_db_path(raw)
        bars, info = load_bars(db, "BTC_USDT", None, None)
        bars_15 = resample(bars, "15m")
        bars_1h = resample(bars, "1h")
        bars_4h = resample(bars, "4h")
        print(f"{db.name} 1m={info.rows} {info.start_ms}..{info.end_ms}")
        for lookback in (10, 12, 14, 16, 18, 20):
            trial = dict(cfg)
            trial["lookback_4h"] = lookback
            trial["lookback_1h"] = lookback
            trial["lookback_15"] = lookback
            trades, _skips = run_mtf(bars, bars_15, bars_1h, bars_4h, trial, {"LONG", "SHORT"})
            closed = [t for t in trades if t["exit_reason"] != "END_OF_DATA"]
            row = _row(db.name, lookback, closed)
            rows.append(row)
            print(json.dumps(row))
    print(json.dumps({"note": "Highest on one file is not a rule.", "rows": rows}, indent=2))


def _row(name, lookback, trades):
    if not trades:
        return {"db": name, "lookback": lookback, "n": 0}
    wins = [t for t in trades if t["net_pnl"] > 0]
    losses = [t for t in trades if t["net_pnl"] <= 0]
    gross_loss = abs(sum(t["net_pnl"] for t in losses))
    equity = peak = dip = 0.0
    for trade in trades:
        equity += trade["r_multiple"]
        peak = max(peak, equity)
        dip = min(dip, equity - peak)
    return {
        "db": name,
        "lookback": lookback,
        "n": len(trades),
        "expectancy_r": round(sum(t["r_multiple"] for t in trades) / len(trades), 4),
        "profit_factor": round(sum(t["net_pnl"] for t in wins) / gross_loss, 4) if gross_loss else None,
        "drawdown_r": round(dip, 2),
        "long_n": sum(t["side"] == "LONG" for t in trades),
        "short_n": sum(t["side"] == "SHORT" for t in trades),
        "long_r": round(sum(t["r_multiple"] for t in trades if t["side"] == "LONG") / max(1, sum(t["side"] == "LONG" for t in trades)), 4),
        "short_r": round(sum(t["r_multiple"] for t in trades if t["side"] == "SHORT") / max(1, sum(t["side"] == "SHORT" for t in trades)), 4),
    }


if __name__ == "__main__":
    main()
