"""Print schema, coverage, and whether 1m exists. Does not run a strategy."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.audit import audit_database, collect_distinct, render_text


def main() -> None:
    explicit = sys.argv[1] if len(sys.argv) > 1 else None
    path = research_db_path(explicit)
    report = audit_database(path)
    symbols, timeframes = collect_distinct(path, report["tables"])
    report["symbol_samples"] = symbols
    report["timeframe_samples"] = timeframes
    report["one_minute_likely"] = _one_minute(report)
    text = render_text(report)
    out = ROOT / "results" / "audit"
    out.mkdir(parents=True, exist_ok=True)
    (out / "audit.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (out / "audit.txt").write_text(text, encoding="utf-8")
    print(text)
    print(f"wrote {out / 'audit.json'}")


def _one_minute(report: dict) -> bool:
    blob = json.dumps(report["timeframe_samples"]).lower() + " " + " ".join(t["name"].lower() for t in report["tables"])
    return any(token in blob for token in ("1m", "min1", "1min"))


if __name__ == "__main__":
    main()
