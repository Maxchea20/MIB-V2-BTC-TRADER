"""Replay the REAL desktop Hunt engine (mib-trader-desktop) on Binance history. Nothing is re-implemented: evaluate_hunt, the weather classifier and the
lifecycle brain (reevaluate / si_checklist) are imported from the desktop repo and called as the live loop calls them. Only the data feed, the fills and the
SL/TP execution are ours.

Phase 1  walk every CLOSED 5m candle (the live windows: 320 closed 15m, 960 5m, 400 1m, 300 4h, 400 1h), call evaluate_hunt with the replay clock (now_ts),
         and record every FIRE. The Hunt state machine does not depend on trade outcomes, so one pass serves both execution models.
Phase 2  trade the FIREs with the live guards (weather block, one position, 15 min cooldown after a HARD_SL), in two models:
  PAPER      what the desktop's own paper pipe assumes: entry at the FIRE price (for the C paths that is a 1m close that had ALREADY closed), exits at the exact SL/TP
             price on 5m bars, lifecycle kills at the 5m close. No slippage, no latency.
  REALISTIC  what MEXC can do: a MARKET order after the FIRE (latency + next 1m open + slippage), SL/TP from the live fill price with the FIRE's distances (as
             _open_live_from_hunt does), attached SL/TP executed on 1m bars by the execution simulator, lifecycle kills as market exits after the closed 5m.
R = net PnL / the planned stop distance (1.5 x 15m ATR), fees 2 bp a side in both models.
Usage: py scripts\\desktop_hunt_replay.py research_binance days=90 desktop=C:\\path\\to\\mib-trader-desktop\\backend [latency=1] [from=2026-01-01 to=2026-03-01]
Needs numpy (the desktop structure code uses it). days=0 or no window = the whole file (slow: the desktop structure builder runs on every 5m close).
"""

import bisect
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from btc_research.config import research_db_path
from btc_research.data.loader import load_bars
from btc_research.data.resample import resample
from btc_research.execution import market_fill, resolve_bar
from btc_research.execution.options import config_from_args

FIVE, FIFTEEN = 300_000, 900_000
FEE = 2.0 / 10_000
COOLDOWN_MS = 3 * 300_000      # autotrader_state CONFIG cooldown_bars_after_failure = 3, _in_cooldown(300)
COOLDOWN_REASONS = ("SL", "BRAIN_EXIT", "FLY", "cancel", "HARD_SL")   # autotrader_loop._in_cooldown


def find_desktop(opt):
    cands = [opt] if opt else []
    cands += [ROOT.parent / "mib-trader-desktop" / "backend", ROOT.parent.parent / "mib-trader-desktop" / "backend", Path("/home/user/maxchea20/mib-trader-desktop/backend")]
    for c in cands:
        if c and (Path(c) / "src" / "brain" / "hunt_brain.py").exists():
            return Path(c)
    raise SystemExit("Desktop backend not found. Pass desktop=<path to mib-trader-desktop\\backend>.")


def load_desktop(path):
    sys.path.insert(0, str(path))
    try:
        import numpy  # noqa: F401
    except ImportError:
        raise SystemExit("numpy is required by the desktop structure code: pip install numpy")
    from types import SimpleNamespace
    from src.brain.hunt_brain import evaluate_hunt, reset_hunt_state
    from src.brain.lifecycle import EXIT, position_from_fire, reevaluate
    from src.brain.lifecycle_tick import si_checklist
    from src.brain.weather import classify, side_allowed
    from src.momentum.observe import observe as obs_mom
    from src.structure.observe import observe as obs_structure
    from src.support_resistance.observe import observe as obs_sr
    return SimpleNamespace(evaluate_hunt=evaluate_hunt, reset_hunt_state=reset_hunt_state, EXIT=EXIT, position_from_fire=position_from_fire, reevaluate=reevaluate,
                           si_checklist=si_checklist, classify=classify, side_allowed=side_allowed, obs_mom=obs_mom, obs_structure=obs_structure, obs_sr=obs_sr)


class Feed:
    """Closed candles only, as dicts the desktop code expects (ts in SECONDS). window(tf, T, limit) = the last `limit` candles that had closed by T."""

    def __init__(self, bars):
        self.series = {tf: resample(bars, tf) for tf in ("5m", "15m", "1h", "4h")}
        self.rows = {"1m": [self.row(b) for b in bars]}
        self.ends = {"1m": [b.close_time for b in bars]}
        for tf, s in self.series.items():
            self.rows[tf] = [self.row(b) for b in s]
            self.ends[tf] = [b.close_time for b in s]

    @staticmethod
    def row(b):
        return {"ts": b.open_time // 1000, "open": b.open, "high": b.high, "low": b.low, "close": b.close, "volume": b.volume}

    def window(self, tf, t_ms, limit):
        k = bisect.bisect_right(self.ends[tf], t_ms)
        return self.rows[tf][max(0, k - limit):k]


class LazyAux(dict):
    """aux for evaluate_hunt: momentum and support/resistance of the 15m window, computed once per distinct 15m window (pure functions of the candles)."""
    cache = {}

    def __init__(self, D, c15):
        super().__init__()
        self.D, self.c15 = D, c15

    def __bool__(self):           # evaluate_hunt does `aux = aux or {}`: an empty dict subclass would be thrown away
        return True

    def get(self, key, default=None):
        if key not in ("mom", "sr"):
            return default
        ck = (key, self.c15[-1]["ts"], len(self.c15))
        if ck not in LazyAux.cache:
            if len(LazyAux.cache) > 4000:
                LazyAux.cache.clear()
            try:
                LazyAux.cache[ck] = (self.D.obs_mom if key == "mom" else self.D.obs_sr)(self.c15, "15m")
            except Exception:
                LazyAux.cache[ck] = None
        return LazyAux.cache[ck]


def generate_fires(D, feed, start_ms, end_ms):
    D.reset_hunt_state()
    fires, states = [], {}
    five = feed.series["5m"]
    todo = [b for b in five if start_ms <= b.close_time < end_ms]
    t0 = time.time()
    for n, b in enumerate(todo):
        T = b.close_time
        c15 = feed.window("15m", T, 320)
        if len(c15) < 60:
            continue
        m5 = feed.window("5m", T, 960)
        m1 = feed.window("1m", T, 400)
        c4 = feed.window("4h", T, 300)
        c1h = feed.window("1h", T, 400)
        weather = D.classify(c4, c1h)
        s1 = None
        for _ in range(3):   # the live loop polls every few seconds: a C watch started on this 5m close resolves on the next poll
            s1 = D.evaluate_hunt(c15, m5[-1], candles_5m=m5, candles_1m=m1, aux=LazyAux(D, c15), now_ts=T // 1000)
            if s1.get("timing_state") != "C_WATCH":
                break
        st = s1.get("timing_state") or s1.get("action")
        states[st] = states.get(st, 0) + 1
        if s1.get("action") == "FIRE":
            fires.append({"T": T, "side": s1["direction"], "entry": float(s1["entry"]), "stop": float(s1["stop"]), "target": float(s1["target"]), "atr": float(s1.get("atr_15m") or 0),
                          "path": s1.get("timing"), "event": s1.get("event"), "slot": s1.get("slot"), "thesis_ts": s1.get("thesis_ts"), "thesis_level": s1.get("thesis_level"),
                          "thesis_invalid": s1.get("thesis_invalid"), "weather": weather.get("flag"), "signal_price": float(m5[-1]["close"])})
        if n and n % 2000 == 0:
            print(f"  ... {n}/{len(todo)} 5m closes, {len(fires)} FIREs, {time.time() - t0:.0f}s", flush=True)
    return fires, states


def _kill_check(D, feed, f, pos, T5_ms, kill_cache):
    """The lifecycle_tick.manage_open_on_5m structure check, from in-memory candles. Returns (structure_event, structure_dir, level_lost) as passed to reevaluate()."""
    w15 = feed.window("15m", T5_ms, 320)
    if len(w15) < 60:
        return None, None, False
    last15 = w15[-1]
    last_ts = int(last15["ts"])
    opened = f["T"] // 1000
    choch_raw, st_ev, st_dir = False, None, None
    if last_ts > opened:
        if last_ts not in kill_cache:
            events = []
            try:
                events = list(getattr(D.obs_structure(w15, "15m"), "events", None) or [])
            except Exception:
                events = []
            kill_cache[last_ts] = events
        for e in kill_cache[last_ts]:
            et = getattr(e, "event_type", "")
            if et in ("CHoCH", "CHOCH") and getattr(e, "timestamp", None) == last15.get("ts"):
                st_ev, st_dir = et, getattr(e, "direction", None)
                sd = (st_dir or "").upper()
                choch_raw = (f["side"] == "LONG" and sd in ("BEARISH", "SHORT", "DOWN")) or (f["side"] == "SHORT" and sd in ("BULLISH", "LONG", "UP"))
                break
    si = D.si_checklist(side=f["side"], opened_at=opened, bar_15m_ts=last_ts, close=float(last15["close"]), choch_against=choch_raw,
                        parent=f.get("thesis_invalid"), level=f.get("thesis_level"))
    return (st_ev if si.get("kill_choch") else None), (st_dir if si.get("kill_choch") else None), bool(si.get("kill_struct"))


def _make_pos(D, f, entry, sl, tp):
    return D.position_from_fire({"direction": f["side"], "entry": entry, "stop": sl, "target": tp, "atr_15m": f["atr"] or abs(entry - sl), "event": f["event"], "why_state": []},
                                trade_id="replay", equity=1000.0, risk_pct=0.02, opened_ts=f["T"] // 1000)


def trade_paper(D, feed, f):
    """The desktop's own paper model, as manage_open_on_5m + paper_trading assume it."""
    sign = 1 if f["side"] == "LONG" else -1
    entry, sl, tp = f["entry"], f["stop"], f["target"]
    pos = _make_pos(D, f, entry, sl, tp)
    kill_cache = {}
    five = feed.series["5m"]
    i = bisect.bisect_right(feed.ends["5m"], f["T"])
    for b in five[i:]:
        ev, dr, lost = _kill_check(D, feed, f, pos, b.close_time, kill_cache)
        rec = D.reevaluate(pos, price=b.close, high=b.high, low=b.low, structure_event=ev, structure_dir=dr, level_lost=lost, now_ts=b.open_time // 1000)
        if rec.get("action") == D.EXIT:
            px = rec.get("exit_px") or b.close
            return done(f, entry, entry, px, px, f["T"], b.close_time, rec.get("exit_kind"), 0.0, 0.0, "PAPER")
    return None


def done(f, entry, entry_raw, exit_px, exit_raw, t_in, t_out, kind, in_slip, out_slip, model):
    sign = 1 if f["side"] == "LONG" else -1
    risk = abs(f["entry"] - f["stop"])
    fees = (entry + exit_px) * FEE
    net = sign * (exit_px - entry) - fees
    return {"model": model, "signal_time": f["T"], "side": f["side"], "path": f["path"], "event": f["event"], "weather": f["weather"], "entry_time": t_in, "entry": entry, "entry_raw": entry_raw,
            "exit_time": t_out, "exit": exit_px, "exit_raw": exit_raw, "exit_kind": kind, "entry_slippage": in_slip, "exit_slippage": out_slip, "risk": risk,
            "r_multiple": net / risk, "gross_r": sign * (exit_raw - entry_raw) / risk, "fire_entry": f["entry"], "signal_price": f["signal_price"]}


def trade_realistic(D, feed, bars, times, f, cfg):
    side, sign = f["side"], (1 if f["side"] == "LONG" else -1)
    fill = market_fill(bars, times, side, f["T"] + cfg.latency_ms, cfg, True, f["signal_price"])
    if fill.status != "FILLED":
        return None
    sl_dist, tp_dist = abs(f["entry"] - f["stop"]), abs(f["target"] - f["entry"])
    ref = fill.raw_price                    # the live loop recomputes SL/TP from the fresh price
    sl, tp = ref - sign * sl_dist, ref + sign * tp_dist
    pos = _make_pos(D, f, ref, sl, tp)
    active = fill.fill_time + cfg.latency_ms
    kill_cache, five_by_open = {}, {b.open_time: b for b in feed.series["5m"]}
    exit_fill, exit_kind = None, None
    for j in range(bisect.bisect_left(times, fill.fill_time), len(bars)):
        b = bars[j]
        if exit_fill is not None and b.open_time >= exit_fill.fill_time:
            return done(f, fill.fill_price, ref, exit_fill.fill_price, exit_fill.raw_price, fill.fill_time, exit_fill.fill_time, exit_kind, fill.slippage, exit_fill.slippage, "REALISTIC")
        if b.open_time >= active:
            ev = resolve_bar(b, side, sl, tp, cfg)
            if ev is not None:
                if ev["reason"] == "UNRESOLVED_BOTH_HIT":
                    return None
                kind = "HARD_SL" if ev["reason"] == "STOP" else "TARGET_REACHED"
                return done(f, fill.fill_price, ref, ev["fill"], ev["raw"], fill.fill_time, ev["time"], kind, fill.slippage, abs(ev["fill"] - ev["raw"]), "REALISTIC")
        if exit_fill is None and b.close_time % FIVE == 0 and b.close_time > fill.fill_time:
            five = five_by_open.get(b.close_time - FIVE)
            if five is None:
                continue
            ev_s, dr, lost = _kill_check(D, feed, f, pos, b.close_time, kill_cache)
            if ev_s is not None or lost:
                rec = D.reevaluate(pos, price=five.close, high=five.close, low=five.close, structure_event=ev_s, structure_dir=dr, level_lost=lost, now_ts=five.open_time // 1000)
                if rec.get("action") == D.EXIT and rec.get("exit_kind") in ("THESIS_FAILURE", "STRUCTURAL_INVALIDATION"):
                    x = market_fill(bars, times, side, b.close_time + cfg.latency_ms, cfg, False)
                    if x.status == "FILLED":
                        exit_fill, exit_kind = x, rec["exit_kind"]
    return None


def run_model(D, feed, bars, times, fires, model, cfg):
    trades, blocked = [], []
    free_at, last_close, last_reason = 0, None, None
    for f in fires:
        if f["T"] < free_at:
            blocked.append((f, "POSITION_OPEN"))
            continue
        if f["weather"] and not D.side_allowed(f["weather"], f["side"]):
            blocked.append((f, "WEATHER_BLOCK"))
            continue
        if last_reason in COOLDOWN_REASONS and last_close is not None and f["T"] - last_close < COOLDOWN_MS:
            blocked.append((f, "COOLDOWN"))
            continue
        t = trade_paper(D, feed, f) if model == "PAPER" else trade_realistic(D, feed, bars, times, f, cfg)
        if t is None:
            blocked.append((f, "NOT_FILLED_OR_OPEN_AT_END"))
            continue
        trades.append(t)
        free_at, last_close, last_reason = t["exit_time"], t["exit_time"], t["exit_kind"]
    return trades, blocked


def stats(label, trades, days):
    if not trades:
        return f"  {label:<10} no trades"
    rs = [t["r_multiple"] for t in trades]
    eq = peak = dip = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dip = min(dip, eq - peak)
    w, l = sum(r for r in rs if r > 0), -sum(r for r in rs if r < 0)
    gross = sum(t["gross_r"] for t in trades) / len(trades)
    hold = sum(t["exit_time"] - t["entry_time"] for t in trades) / len(trades) / 3_600_000
    return (f"  {label:<10} n={len(rs):4d} {len(rs) / max(days, 1):4.2f}/day hold {hold:5.1f}h  win {sum(r > 0 for r in rs) / len(rs):3.0%}  gross {gross:+.3f}R  net {sum(rs) / len(rs):+.3f}R  "
            f"PF(R) {w / l if l else 9.99:4.2f}  total {sum(rs):+6.1f}R  dip {dip:6.1f}R")


def main():
    cfg, rest = config_from_args(sys.argv[1:])
    opts = dict(a.split("=", 1) for a in rest if "=" in a)
    pos = [a for a in rest if "=" not in a]
    name = pos[0] if pos else "research_binance"
    D = load_desktop(find_desktop(opts.get("desktop")))
    bars, _ = load_bars(research_db_path(f"backend/{name}.db"), "BTC_USDT", None, None)
    first, last = bars[0].open_time, bars[-1].close_time
    start = int(datetime.fromisoformat(opts["from"]).replace(tzinfo=timezone.utc).timestamp() * 1000) if "from" in opts else first
    end = int(datetime.fromisoformat(opts["to"]).replace(tzinfo=timezone.utc).timestamp() * 1000) if "to" in opts else last
    days_opt = int(opts.get("days", 90))
    if days_opt and "from" not in opts:
        start = max(first, end - days_opt * 86_400_000)
    warm = start - 56 * 86_400_000
    cut = bisect.bisect_left([b.open_time for b in bars], max(first, warm))
    bars = bars[cut:]
    times = [b.open_time for b in bars]
    feed = Feed(bars)
    days = (end - start) / 86_400_000
    print(f"{name}: replaying the REAL desktop Hunt on {days:.0f} days ({datetime.fromtimestamp(start / 1000, timezone.utc):%Y-%m-%d} to {datetime.fromtimestamp(end / 1000, timezone.utc):%Y-%m-%d}), latency {cfg.execution_latency_seconds}s", flush=True)
    fires, states = generate_fires(D, feed, start, end)
    print(f"Hunt FIREs: {len(fires)}   brain states per 5m close: {dict(sorted(states.items(), key=lambda kv: -kv[1]))}")
    by_path = {}
    for f in fires:
        by_path[f['path']] = by_path.get(f['path'], 0) + 1
    print(f"FIREs by path: {by_path}")
    out = {}
    for model in ("PAPER", "REALISTIC"):
        trades, blocked = run_model(D, feed, bars, times, fires, model, cfg)
        why = {}
        for _, r in blocked:
            why[r] = why.get(r, 0) + 1
        out[model] = (trades, blocked)
        print(f"\n{model}: trades {len(trades)}; FIREs not traded: {why}")
        print(stats("all", trades, days))
        for key in ("path", "event", "weather", "side", "exit_kind"):
            vals = sorted({t[key] for t in trades}, key=lambda v: str(v))
            for v in vals:
                print(stats(f"{key}={v}"[:10] if False else f"  {v}", [t for t in trades if t[key] == v], days) if False else stats(f"{key[:4]}={v}", [t for t in trades if t[key] == v], days))
    folder = ROOT / "results" / "desktop_replay" / name
    folder.mkdir(parents=True, exist_ok=True)
    for model, (trades, blocked) in out.items():
        if trades:
            with (folder / f"trades_{model.lower()}.csv").open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, list(trades[0].keys()))
                w.writeheader()
                w.writerows(trades)
    with (folder / "fires.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, list(fires[0].keys()) if fires else ["T"])
        w.writeheader()
        w.writerows(fires)
    print(f"\nfiles: {folder}")


if __name__ == "__main__":
    main()
