"""Count 4h range states. No orders."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.market_structure.range_detector import RangeParams, detect_range


def main():
    db = research_db_path(sys.argv[1] if len(sys.argv) > 1 else None)
    bars, info = load_bars(db, "BTC_USDT", None, None)
    bars_4h = resample(bars, "4h")
    print(f"{db.name} 4h={len(bars_4h)} {info.start_ms}..{info.end_ms}")
    rows = []
    for lookback in (30, 48):
        params = RangeParams(lookback=lookback)
        checked = score85 = 0
        for i in range(lookback, len(bars_4h)):
            state = detect_range(bars_4h[i - lookback + 1 : i + 1], None, params)
            checked += 1
            score85 += state.score >= 85
        rows.append({"lookback": lookback, "checked": checked, "score_85_share": round(score85 / checked, 4) if checked else 0})
    print(json.dumps({"rows": rows}, indent=2))


if __name__ == "__main__":
    main()
