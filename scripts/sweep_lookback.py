"""Same 20-bar entry with a shorter 15m lookback. One window. Not a selection rule."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.setups.hunt_lookback import run_hunt20


def main():
    lengths = [int(x) for x in sys.argv[1:]] or [20, 19, 18, 16, 15]
    db = research_db_path(None)
    bars, info = load_bars(db, "BTC_USDT", None, None)
    bars_5 = resample(bars, "5m")
    bars_15 = resample(bars, "15m")
    print(f"1m bars={info.rows} {info.start_ms}..{info.end_ms}")
    rows = []
    base = {
        "lookback_5": 50,
        "atr_period": 14,
        "sl_atr": 1.5,
        "tp_atr": 2.5,
        "entry_mode": "break",
        "quiet_minutes": 15,
        "fee_bps_per_side": 2.0,
        "slippage_ticks": 1,
        "slippage_bps": 0.5,
        "tick_size": 0.1,
    }
    for length in lengths:
        cfg = dict(base, lookback_15=length)
        trades, _skips = run_hunt20(bars, bars_5, bars_15, cfg, {"LONG", "SHORT"})
        closed = [t for t in trades if t["exit_reason"] != "END_OF_DATA"]
        rows.append(_row(length, closed))
        print(json.dumps(rows[-1]))
    print(json.dumps({"note": "Highest on this down window is not a rule.", "rows": rows}, indent=2))


def _row(length, trades):
    if not trades:
        return {"lookback_15": length, "n": 0}
    wins = [t for t in trades if t["net_pnl"] > 0]
    losses = [t for t in trades if t["net_pnl"] <= 0]
    gross_win = sum(t["net_pnl"] for t in wins)
    gross_loss = abs(sum(t["net_pnl"] for t in losses))
    return {
        "lookback_15": length,
        "n": len(trades),
        "expectancy_r": round(sum(t["r_multiple"] for t in trades) / len(trades), 4),
        "win_rate": round(len(wins) / len(trades), 4),
        "profit_factor": round(gross_win / gross_loss, 4) if gross_loss else None,
        "long_n": sum(t["side"] == "LONG" for t in trades),
        "short_n": sum(t["side"] == "SHORT" for t in trades),
        "long_r": round(sum(t["r_multiple"] for t in trades if t["side"] == "LONG") / max(1, sum(t["side"] == "LONG" for t in trades)), 4),
        "short_r": round(sum(t["r_multiple"] for t in trades if t["side"] == "SHORT") / max(1, sum(t["side"] == "SHORT" for t in trades)), 4),
    }


if __name__ == "__main__":
    main()
