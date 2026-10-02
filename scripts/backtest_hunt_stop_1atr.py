"""Full Hunt with the stop at 1 ATR. Target stays 2.5 ATR."""

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import backtest_desktop_cfi as hunt


def main():
    db_arg = sys.argv[1] if len(sys.argv) > 1 else None
    from btc_research.config import research_db_path
    from btc_research.data.loader import load_bars
    from btc_research.data.resample import resample

    db = research_db_path(db_arg)
    bars, info = load_bars(db, "BTC_USDT", None, None)
    print(f"{db.name} 1m={info.rows} stop_atr=1 target_atr=2.5")
    trades = _run(bars, resample(bars, "5m"), resample(bars, "15m"), resample(bars, "1h"), resample(bars, "4h"))
    folder = ROOT.parent / "results" / "exp-hunt-stop-1atr" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "trades.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, hunt.FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(trades)
    row = hunt._score(db.name, trades)
    row["stop_atr"] = 1.0
    row["target_atr"] = 2.5
    row["file"] = str(folder / "trades.csv")
    print(json.dumps(row, indent=2))


def _run(bars, bars_5, bars_15, bars_1h, bars_4h):
    trades = []
    open_trade = None
    quiet_until = 0
    atrs = hunt._atr(bars_15)
    atrs_4h = hunt._atr(bars_4h)
    fast = hunt._events(bars_15, 5)
    internal = hunt._events(bars_15, 2)
    for j, bar in enumerate(bars_5):
        slot_start = (bar.open_time // hunt.FIFTEEN) * hunt.FIFTEEN
        if bar.open_time not in (slot_start, slot_start + hunt.FIVE, slot_start + 2 * hunt.FIVE):
            continue
        slot = (bar.open_time - slot_start) // hunt.FIVE + 1
        live = [b for b in bars_5[max(0, j - 2):j + 1] if b.open_time >= slot_start]
        j15 = hunt._closed(bars_15, slot_start, hunt.FIFTEEN)
        j4 = hunt._closed(bars_4h, bar.open_time + hunt.FIVE, 14_400_000)
        j1 = hunt._closed(bars_1h, bar.open_time + hunt.FIVE, 3_600_000)
        if j15 < 60 or j4 < 20 or not atrs[j15 - 1]:
            continue
        side, event, gate = hunt._gate(fast, internal, j15)
        if not side:
            continue
        flag = hunt._weather(bars_4h[:j4], bars_1h[:j1], atrs_4h)
        if flag == "SWING_UP" and side != "LONG":
            continue
        if flag == "SWING_DOWN" and side != "SHORT":
            continue
        level = bars_15[j15 - 1].high if side == "LONG" else bars_15[j15 - 1].low
        if not hunt._answers(side, level, live, slot, atrs[j15 - 1]):
            continue
        entry_time = bar.open_time + hunt.FIVE
        if open_trade and entry_time >= open_trade["entry_time"]:
            done = hunt._walk(open_trade, bars, open_trade["entry_time"], entry_time)
            if done:
                trades.append(done)
                quiet_until = done["exit_time"] + 15 * 60_000
                open_trade = None
            else:
                continue
        if entry_time < quiet_until:
            continue
        atr = atrs[j15 - 1]
        slip = 0.1 + level * 0.00005
        entry = level + slip if side == "LONG" else level - slip
        open_trade = {
            "side": side, "event": event, "gate": gate, "weather": flag,
            "entry": entry,
            "stop": entry - atr if side == "LONG" else entry + atr,
            "target": entry + 2.5 * atr if side == "LONG" else entry - 2.5 * atr,
            "arm": entry, "atr": atr, "trail": False, "risk": atr, "entry_time": entry_time,
        }
        done = hunt._walk(open_trade, bars, entry_time, entry_time + hunt.FIVE)
        if done:
            trades.append(done)
            quiet_until = done["exit_time"] + 15 * 60_000
            open_trade = None
    if open_trade:
        done = hunt._walk(open_trade, bars, open_trade["entry_time"], bars[-1].open_time + 60_000)
        if done:
            trades.append(done)
    return [t for t in trades if t["exit_reason"] != "END_OF_DATA"]


if __name__ == "__main__":
    main()
