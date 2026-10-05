"""Your chart reading, tested: in a SWING a CHoCH confirms a solid swing (follow it); in CHOP the move after a CHoCH is often exhausted and reverts (fade it).
Hunt V4 does not do this: BOS/CHoCH is only a label and chop weather uses the same breakout logic as swing weather. Nothing here changes Hunt.
Every Hunt FIRE (the signal conditions are untouched, one-position rule NOT applied so every signal is measured) is simulated twice with the realistic execution model:
  FOLLOW  the Hunt trade (the side of the latest 15m swing, market order after the closed 5m candle + latency, stop 1.5 / target 2.5 x 15m ATR, floors)
  FADE    the opposite side: same entry time, same distances, same floors, same costs
Grouped by weather (swing = SWING_UP/SWING_DOWN, chop = CHOP) x event (CHoCH, BOS). 'gross' = before slippage and fees, 'net' = after.
Your idea is supported only if, in CHOP+CHoCH, FADE net is clearly better than FOLLOW net AND positive, and in SWING+CHoCH FOLLOW net is positive. The +/- is a naive standard error; neighbouring signals overlap, so the real uncertainty is larger.
Usage: py scripts\\choch_regime_test.py research_binance [latency=1]
"""

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.execution import market_fill
from btc_research.execution.options import config_from_args
from btc_research.setups import hunt_exits

import backtest_desktop_cfi as eng


def simulate(bars, times, end, fire, side, cfg):
    sign = 1 if side == "LONG" else -1
    fill = market_fill(bars, times, side, fire["signal_time"] + cfg.latency_ms, cfg, entering=True, intended=fire["signal_price"])
    if fill.status != "FILLED":
        return None
    entry, atr = fill.fill_price, fire["atr"]
    trade = {"side": side, "entry": entry, "entry_raw": fill.raw_price, "stop": entry - sign * 1.5 * atr, "target": entry + sign * 2.5 * atr,
             "risk": 1.5 * atr, "atr": atr, "entry_time": fill.fill_time}
    done = hunt_exits.walk(trade, bars, fill.fill_time, end, "floors", cfg)
    if not done or done["r_multiple"] is None:
        return None
    return done["r_multiple"], done["gross_r_before_costs"]


def cell(rows):
    n = len(rows)
    if n < 2:
        return f"{n:5d}   -"
    net = [r[0] for r in rows]
    gross = [r[1] for r in rows]
    m = sum(net) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in net) / (n - 1))
    return f"net {m:+.3f}R (+/-{sd / math.sqrt(n):.3f})  gross {sum(gross) / n:+.3f}R"


def main():
    cfg, rest = config_from_args(sys.argv[1:])
    name = rest[0] if rest else "research_binance"
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    times = [b.open_time for b in bars]
    end = bars[-1].open_time + 60_000
    r = [resample(bars, x) for x in ("5m", "15m", "1h", "4h")]
    events = []
    eng._run(bars, *r, False, None, False, "floors", False, cfg, events)
    fires = [e for e in events]
    print(f"{name}: {len(fires)} Hunt FIREs, each simulated as FOLLOW and as FADE under realistic execution (latency {cfg.execution_latency_seconds}s)", flush=True)
    groups = {}
    for k, f in enumerate(fires):
        follow = simulate(bars, times, end, f, f["signal_side"], cfg)
        fade = simulate(bars, times, end, f, "SHORT" if f["signal_side"] == "LONG" else "LONG", cfg)
        if follow is None or fade is None:
            continue
        w = "swing" if f["weather"] in ("SWING_UP", "SWING_DOWN") else "chop"
        for key in ((w, f["event"]), (w, "all"), ("all", f["event"]), ("all", "all")):
            groups.setdefault(key, []).append((follow, fade))
    print(f"\n  {'weather':<7} {'event':<6} {'signals':>7}   FOLLOW (what Hunt does)                      FADE (the opposite trade)")
    for key in (("swing", "CHoCH"), ("swing", "BOS"), ("swing", "all"), ("chop", "CHoCH"), ("chop", "BOS"), ("chop", "all"), ("all", "CHoCH"), ("all", "BOS"), ("all", "all")):
        rows = groups.get(key, [])
        if not rows:
            continue
        print(f"  {key[0]:<7} {key[1]:<6} {len(rows):7d}   {cell([x[0] for x in rows]):<46} {cell([x[1] for x in rows])}")


if __name__ == "__main__":
    main()
