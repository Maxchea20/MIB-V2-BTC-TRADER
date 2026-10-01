"""SQLite schema audit. Does not assume table or column names."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

OHLC = {"open", "high", "low", "close"}
TIME_HINTS = ("time", "ts", "timestamp", "open_time", "date", "t")
VOLUME_HINTS = ("volume", "vol", "qty", "base_volume")
SYMBOL_HINTS = ("symbol", "pair", "ticker")
TF_HINTS = ("interval", "timeframe", "tf", "resolution")


def connect(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise SystemExit(
            f"Research database not found: {path}\n"
            "Copy the Binance file to backend/research_binance.db or pass --db / set RESEARCH_DB_PATH."
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _columns(conn, table: str):
    rows = conn.execute(f"PRAGMA table_info({quote(table)})").fetchall()
    return [{"name": r["name"], "type": r["type"]} for r in rows]


def audit_database(path: Path) -> dict:
    conn = connect(path)
    tables = [r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    report_tables = []
    for table in tables:
        cols = _columns(conn, table)
        count = conn.execute(f"SELECT COUNT(*) AS n FROM {quote(table)}").fetchone()["n"]
        lower = {c["name"].lower(): c["name"] for c in cols}
        time_cols = [lower[k] for k in lower if any(h in k for h in TIME_HINTS)]
        bounds = {}
        for col in time_cols[:3]:
            try:
                row = conn.execute(f"SELECT MIN({quote(col)}) AS lo, MAX({quote(col)}) AS hi, COUNT({quote(col)}) AS n FROM {quote(table)}").fetchone()
                bounds[col] = {"min": row["lo"], "max": row["hi"], "non_null": row["n"]}
            except sqlite3.Error as exc:
                bounds[col] = {"error": str(exc)}
        sample = conn.execute(f"SELECT * FROM {quote(table)} LIMIT 1").fetchone()
        report_tables.append({
            "name": table,
            "rows": count,
            "columns": cols,
            "has_ohlc": OHLC.issubset(set(lower)),
            "time_candidates": time_cols,
            "time_bounds": bounds,
            "volume_candidates": [lower[k] for k in lower if any(h in k for h in VOLUME_HINTS)],
            "symbol_candidates": [lower[k] for k in lower if any(h in k for h in SYMBOL_HINTS)],
            "timeframe_candidates": [lower[k] for k in lower if any(h in k for h in TF_HINTS)],
            "sample": dict(sample) if sample else None,
        })
    conn.close()
    return {"path": str(path), "tables": report_tables, "symbol_samples": {}, "timeframe_samples": {}, "one_minute_likely": False, "higher_timeframes_stored": {}}


def collect_distinct(path: Path, tables: list[dict]):
    conn = connect(path)
    symbols, timeframes = {}, {}
    for table in tables:
        if table["rows"] == 0:
            continue
        for col in table["symbol_candidates"]:
            try:
                rows = conn.execute(f"SELECT {quote(col)} AS v, COUNT(*) AS n FROM {quote(table['name'])} GROUP BY 1 ORDER BY n DESC LIMIT 20").fetchall()
                symbols[f"{table['name']}.{col}"] = [dict(r) for r in rows]
            except sqlite3.Error:
                continue
        for col in table["timeframe_candidates"]:
            try:
                rows = conn.execute(f"SELECT {quote(col)} AS v, COUNT(*) AS n FROM {quote(table['name'])} GROUP BY 1 ORDER BY n DESC LIMIT 20").fetchall()
                timeframes[f"{table['name']}.{col}"] = [dict(r) for r in rows]
            except sqlite3.Error:
                continue
    conn.close()
    return symbols, timeframes


def render_text(report: dict) -> str:
    lines = [f"database: {report['path']}", f"tables: {len(report['tables'])}"]
    for table in report["tables"]:
        lines.append("")
        lines.append(f"TABLE {table['name']} rows={table['rows']} ohlc={table['has_ohlc']}")
        lines.append("  columns: " + ", ".join(f"{c['name']}:{c['type']}" for c in table["columns"]))
        lines.append(f"  time_candidates: {table['time_candidates']} bounds={table['time_bounds']}")
        lines.append(f"  volume: {table['volume_candidates']} symbol: {table['symbol_candidates']} tf: {table['timeframe_candidates']}")
    lines.append("")
    lines.append(f"symbol_samples: {report['symbol_samples']}")
    lines.append(f"timeframe_samples: {report['timeframe_samples']}")
    lines.append(f"one_minute_likely: {report['one_minute_likely']}")
    if not report["one_minute_likely"]:
        lines.append("MISSING: no 1m token found. S1 needs 1m opens. Do not substitute market_data_clean.db.")
    return "\n".join(lines) + "\n"
