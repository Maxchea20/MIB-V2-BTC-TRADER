"""Paths and experiment config. No exchange calls."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return ROOT


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def default_config() -> dict:
    return load_json(ROOT / "config" / "default.json")


def experiment_config(experiment_id: str) -> dict:
    path = ROOT / "config" / "experiments" / f"{experiment_id}.json"
    if not path.exists():
        known = sorted(p.stem for p in (ROOT / "config" / "experiments").glob("*.json"))
        raise SystemExit(f"Unknown experiment {experiment_id}. Known: {known}")
    base = default_config()
    exp = load_json(path)
    return {**base, **exp}


def research_db_path(explicit: str | None = None) -> Path:
    raw = explicit or os.environ.get("RESEARCH_DB_PATH") or default_config()["research_db"]
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    if "market_data_clean" in path.name.lower():
        raise SystemExit("Refusing to backtest market_data_clean.db. Research must use research_binance.db.")
    return path


def live_db_path() -> Path:
    raw = os.environ.get("LIVE_DB_PATH") or default_config()["live_db"]
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path
