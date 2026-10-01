"""Run one pre-registered experiment locally. Does not upload candles."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research import __version__
from btc_research.config import experiment_config, research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.research.report import write_run
from btc_research.setups.s1_pullback import run_s1
from btc_research.setups.s2_sweep import run_s2
from btc_research.setups.s3_retest import run_s3
from btc_research.setups.s4_range import run_s4
from btc_research.setups.w1_swing import run_w1
from btc_research.setups.hunt_cfi import run_hunt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--db", default=None)
    parser.add_argument("--side", choices=["LONG", "SHORT", "BOTH"], default="BOTH")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    args = parser.parse_args()
    cfg = experiment_config(args.experiment)
    allowed = {
        "exp-s1-structure-v1",
        "exp-s1-exit-075-120",
        "exp-s1-target-1r",
        "exp-s2-structure-v1",
        "exp-s3-structure-v1",
        "exp-s4-structure-v1",
        "exp-w1-structure-v1",
        "exp-hunt-cfi-v1",
    }
    if args.experiment not in allowed:
        raise SystemExit("Implemented experiments: S1, S1 exit 0.75/1.2, S1 target 1R, S2, S3, S4, W1, Hunt C-FI.")
    db = research_db_path(args.db)
    start = _ms(args.start or cfg.get("start"))
    end = _ms(args.end or cfg.get("end"))
    sides = {"LONG", "SHORT"} if args.side == "BOTH" else {args.side}
    print(f"loading {db}")
    bars, info = load_bars(db, cfg.get("symbol") or "BTCUSDT", start, end)
    print(f"1m bars={info.rows} table={info.table} {info.start_ms}..{info.end_ms}")
    bars_5 = resample(bars, "5m")
    bars_15 = resample(bars, "15m")
    family = cfg.get("family")
    if family == "S1":
        bars_1h = resample(bars, "1h")
        print(f"resampled 5m={len(bars_5)} 15m={len(bars_15)} 1h={len(bars_1h)}")
        trades, skips = run_s1(bars, bars_5, bars_15, bars_1h, cfg, sides)
    elif family == "S3":
        print(f"resampled 5m={len(bars_5)} 15m={len(bars_15)}")
        trades, skips = run_s3(bars, bars_5, bars_15, cfg, sides)
    elif family == "S4":
        print(f"resampled 15m={len(bars_15)}")
        trades, skips = run_s4(bars, bars_15, cfg, sides)
    elif family == "W1":
        bars_1h = resample(bars, "1h")
        bars_4h = resample(bars, "4h")
        bars_1d = resample(bars, "1d")
        print(f"resampled 15m={len(bars_15)} 1h={len(bars_1h)} 4h={len(bars_4h)} 1d={len(bars_1d)}")
        trades, skips = run_w1(bars, bars_15, bars_1h, bars_4h, bars_1d, cfg, sides)
    elif family == "HUNT":
        bars_4h = resample(bars, "4h")
        print(f"resampled 5m={len(bars_5)} 15m={len(bars_15)} 4h={len(bars_4h)}")
        trades, skips = run_hunt(bars, bars_5, bars_15, bars_4h, cfg, sides)
    else:
        print(f"resampled 5m={len(bars_5)} 15m={len(bars_15)}")
        trades, skips = run_s2(bars, bars_5, bars_15, cfg, sides)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    meta = {
        "experiment_id": args.experiment,
        "code_version": __version__,
        "git_commit": _git(),
        "database": str(db),
        "source": "research_binance",
        "symbol": cfg.get("symbol"),
        "load": info.__dict__,
        "side_filter": args.side,
        "start": start,
        "end": end,
        "config_sha256": hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest(),
        "funding_status": "MISSING_NOT_APPLIED",
    }
    write_run(ROOT / "results" / args.experiment / run_id, cfg, trades, skips, meta)


def _ms(value):
    if not value:
        return None
    return int(datetime.fromisoformat(str(value)).replace(tzinfo=timezone.utc).timestamp() * 1000)


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


if __name__ == "__main__":
    main()
