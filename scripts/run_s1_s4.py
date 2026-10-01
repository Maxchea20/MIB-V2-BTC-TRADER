"""Rerun the four scalp structure experiments and print one table."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import experiment_config, research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.setups.s1_pullback import run_s1
from btc_research.setups.s2_sweep import run_s2
from btc_research.setups.s3_retest import run_s3
from btc_research.setups.s4_range import run_s4


def main():
    db = research_db_path(None)
    bars, info = load_bars(db, "BTC_USDT", None, None)
    bars_5 = resample(bars, "5m")
    bars_15 = resample(bars, "15m")
    bars_1h = resample(bars, "1h")
    print(f"1m bars={info.rows} {info.start_ms}..{info.end_ms}")
    rows = []
    for name, runner, extra in (
        ("exp-s1-structure-v1", run_s1, (bars_1h,)),
        ("exp-s2-structure-v1", run_s2, ()),
        ("exp-s3-structure-v1", run_s3, ()),
        ("exp-s4-structure-v1", run_s4, ()),
    ):
        cfg = experiment_config(name)
        if name == "exp-s1-structure-v1":
            trades, _skips = runner(bars, bars_5, bars_15, bars_1h, cfg, {"LONG", "SHORT"})
        elif name == "exp-s4-structure-v1":
            trades, _skips = runner(bars, bars_15, cfg, {"LONG", "SHORT"})
        else:
            trades, _skips = runner(bars, bars_5, bars_15, cfg, {"LONG", "SHORT"})
        closed = [t for t in trades if t["exit_reason"] != "END_OF_DATA"]
        rows.append(_row(name, closed))
        print(json.dumps(rows[-1]))
    print(json.dumps({"rows": rows}, indent=2))


def _row(name, trades):
    if not trades:
        return {"experiment": name, "n": 0}
    wins = [t for t in trades if t["net_pnl"] > 0]
    losses = [t for t in trades if t["net_pnl"] <= 0]
    gross_loss = abs(sum(t["net_pnl"] for t in losses))
    return {
        "experiment": name,
        "n": len(trades),
        "expectancy_r": round(sum(t["r_multiple"] for t in trades) / len(trades), 4),
        "win_rate": round(len(wins) / len(trades), 4),
        "profit_factor": round(sum(t["net_pnl"] for t in wins) / gross_loss, 4) if gross_loss else None,
        "long_n": sum(t["side"] == "LONG" for t in trades),
        "short_n": sum(t["side"] == "SHORT" for t in trades),
        "long_r": round(sum(t["r_multiple"] for t in trades if t["side"] == "LONG") / max(1, sum(t["side"] == "LONG" for t in trades)), 4),
        "short_r": round(sum(t["r_multiple"] for t in trades if t["side"] == "SHORT") / max(1, sum(t["side"] == "SHORT" for t in trades)), 4),
    }


if __name__ == "__main__":
    main()
