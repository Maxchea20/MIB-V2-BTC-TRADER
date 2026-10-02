"""Count range states on the research year. No orders."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.market_structure.range_detector import detect_range


def main():
    db = research_db_path(sys.argv[1] if len(sys.argv) > 1 else None)
    bars, info = load_bars(db, "BTC_USDT", None, None)
    bars_15 = resample(bars, "15m")
    bars_1h = resample(bars, "1h")
    print(f"{db.name} 15m={len(bars_15)} 1h={len(bars_1h)} {info.start_ms}..{info.end_ms}")
    active = 0
    checked = 0
    scores = []
    for i in range(80, len(bars_15)):
        hour_end = bars_15[i].open_time
        hour = [b for b in bars_1h if b.open_time + 3_600_000 <= hour_end][-80:]
        state = detect_range(bars_15[: i + 1], hour or None)
        checked += 1
        active += state.active
        if state.active:
            scores.append(state.score)
    print(json.dumps({
        "checked": checked,
        "active_bars": active,
        "active_share": round(active / checked, 4) if checked else 0,
        "median_score": sorted(scores)[len(scores) // 2] if scores else None,
    }, indent=2))


if __name__ == "__main__":
    main()
