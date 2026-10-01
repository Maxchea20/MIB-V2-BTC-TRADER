"""Load Binance research candles without assuming a fixed schema."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from btc_research.data.audit import connect, quote

OHLC_ALIASES = {
    "open": ("open", "o", "open_price"),
    "high": ("high", "h", "high_price"),
    "low": ("low", "l", "low_price"),
    "close": ("close", "c", "close_price"),
    "volume": ("volume", "vol", "base_volume", "q", "qty"),
}
TIME_ALIASES = ("open_time", "timestamp", "time", "ts", "t", "date")


@dataclass
class Bar:
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class LoadInfo:
    table: str
    time_col: str
    columns: dict
    symbol: str | None
    timeframe: str | None
    rows: int
    start_ms: int
    end_ms: int
    candidates: list


def load_bars(path: Path, symbol: str, start_ms: int | None = None, end_ms: int | None = None):
    conn = connect(path)
    spec = detect_ohlcv_table(conn)
    bars = _read(conn, spec, symbol, start_ms, end_ms)
    conn.close()
    if not bars:
        raise SystemExit(f"No candles loaded from {spec['table']} for symbol {symbol}. Run the audit.")
    _require_one_minute(bars)
    info = LoadInfo(spec["table"], spec["time_col"], spec["columns"], spec.get("symbol_col"), spec.get("tf_value") or spec.get("tf_col"), len(bars), bars[0].open_time, bars[-1].open_time, spec["detected_candidates"])
    return bars, info


def detect_ohlcv_table(conn):
    tables = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    candidates = []
    for table in tables:
        cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({quote(table)})")]
        lower = {c.lower(): c for c in cols}
        mapped = {}
        for key, aliases in OHLC_ALIASES.items():
            for alias in aliases:
                if alias in lower:
                    mapped[key] = lower[alias]
                    break
        if not {"open", "high", "low", "close"}.issubset(mapped):
            continue
        time_col = next((lower[a] for a in TIME_ALIASES if a in lower), None)
        if time_col is None:
            continue
        score = 5 if any(token in table.lower() for token in ("1m", "min1", "m1")) else 0
        candidates.append({"table": table, "columns": mapped, "time_col": time_col, "symbol_col": lower.get("symbol") or lower.get("pair"), "tf_col": lower.get("interval") or lower.get("timeframe") or lower.get("tf"), "score": score})
    if not candidates:
        raise SystemExit("Could not find an OHLCV table. No silent substitute.")
    candidates.sort(key=lambda item: item["score"], reverse=True)
    chosen = candidates[0]
    chosen["tf_value"] = _preferred_timeframe(conn, chosen)
    chosen["detected_candidates"] = [c["table"] for c in candidates]
    return chosen


def _preferred_timeframe(conn, spec):
    if not spec.get("tf_col"):
        return None
    rows = conn.execute(f"SELECT {quote(spec['tf_col'])} AS v FROM {quote(spec['table'])} GROUP BY 1").fetchall()
    values = [str(r["v"]) for r in rows]
    for preferred in ("1m", "1M", "Min1", "min1", "M1"):
        if preferred in values:
            return preferred
    return None


def _read(conn, spec, symbol, start_ms, end_ms):
    cols = spec["columns"]
    volume_sql = quote(cols["volume"]) if "volume" in cols else "0"
    select = ", ".join([quote(spec["time_col"]), quote(cols["open"]), quote(cols["high"]), quote(cols["low"]), quote(cols["close"]), volume_sql])
    where, params = [], []
    if spec.get("symbol_col"):
        where.append(f"{quote(spec['symbol_col'])} = ?")
        params.append(symbol)
    if spec.get("tf_col") and spec.get("tf_value"):
        where.append(f"{quote(spec['tf_col'])} = ?")
        params.append(spec["tf_value"])
    sql = f"SELECT {select} FROM {quote(spec['table'])}"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {quote(spec['time_col'])} ASC"
    bars = []
    for row in conn.execute(sql, params):
        open_time = to_ms(row[0])
        if start_ms is not None and open_time < start_ms:
            continue
        if end_ms is not None and open_time >= end_ms:
            break
        bars.append(Bar(open_time, open_time + 60_000, float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5] or 0)))
    return bars


def to_ms(value) -> int:
    if isinstance(value, (int, float)):
        num = int(value)
        return num * 1000 if num < 10_000_000_000 else num
    return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp() * 1000)


def _require_one_minute(bars):
    deltas = [bars[i + 1].open_time - bars[i].open_time for i in range(min(2000, len(bars) - 1))]
    deltas = [d for d in deltas if d > 0]
    if not deltas:
        raise SystemExit("Candle timestamps do not advance.")
    median = sorted(deltas)[len(deltas) // 2]
    if median > 90_000:
        raise SystemExit(f"Median bar spacing is {median} ms, not 1 minute. Missing 1m is a data gap. Do not use market_data_clean.db.")
    for bar in bars:
        bar.close_time = bar.open_time + median
