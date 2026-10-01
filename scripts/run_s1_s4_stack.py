"""S1 to S4 on the 4h side, 1h structure, 15m trigger stack."""

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
    bars_4h = resample(bars, "4h")
    print(f"1m bars={info.rows} {info.start_ms}..{info.end_ms}")
    sides = {"LONG", "SHORT"}
    jobs = (
        ("S1_stack", "exp-s1-structure-v1", lambda cfg: run_s1(bars_5, bars_15, bars_1h, bars_4h, cfg, sides)),
        ("S2_stack", "exp-s2-structure-v1", lambda cfg: run_s2(bars_5, bars_15, bars_1h, cfg, sides)),
        ("S3_stack", "exp-s3-structure-v1", lambda cfg: run_s3(bars_5, bars_15, bars_1h, cfg, sides)),
        ("S4_stack", "exp-s4-structure-v1", lambda cfg: run_s4(bars_5, bars_1h, cfg, sides)),
    )
    rows = []
    for label, config_name, runner in jobs:
        cfg = experiment_config(config_name)
        trades, _skips = runner(cfg)
        closed = [t for t in trades if t["exit_reason"] != "END_OF_DATA"]
        matched = [t for t in closed if _trend(bars_4h, t["decision_time"]) == t["side"]]
        rows.append(_row(label, matched, cfg.get("fee_bps_per_side")))
        print(json.dumps(rows[-1]))
    print(json.dumps({"note": "4h close versus 20 bars must match the side. S1 bias is the 4h swing. Entry is the next 5m open.", "rows": rows}, indent=2))


def _trend(bars, now):
    closed = [b for b in bars if b.close_time <= now]
    if len(closed) <= 20:
        return None
    if closed[-1].close > closed[-21].close:
        return "LONG"
    if closed[-1].close < closed[-21].close:
        return "SHORT"
    return None


def _row(name, trades, fee):
    if not trades:
        return {"setup": name, "n": 0, "fee_bps_per_side": fee}
    wins = [t for t in trades if t["net_pnl"] > 0]
    losses = [t for t in trades if t["net_pnl"] <= 0]
    gross_loss = abs(sum(t["net_pnl"] for t in losses))
    return {
        "setup": name,
        "n": len(trades),
        "fee_bps_per_side": fee,
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
