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
    checked = score70 = score85 = score100 = hour_range = 0
    hour_i = 0
    for i in range(80, len(bars_15)):
        hour_end = bars_15[i].open_time
        while hour_i < len(bars_1h) and bars_1h[hour_i].open_time + 3_600_000 <= hour_end:
            hour_i += 1
        state = detect_range(bars_15[max(0, i - 79): i + 1], bars_1h[max(0, hour_i - 80):hour_i] or None)
        checked += 1
        score70 += state.score >= 70
        score85 += state.score >= 85
        score100 += state.score >= 100
        hour_range += state.context == "RANGE"
    print(json.dumps({
        "checked": checked,
        "score_70_share": round(score70 / checked, 4),
        "score_85_share": round(score85 / checked, 4),
        "score_100_share": round(score100 / checked, 4),
        "hour_range_share": round(hour_range / checked, 4),
    }, indent=2))


if __name__ == "__main__":
    main()
