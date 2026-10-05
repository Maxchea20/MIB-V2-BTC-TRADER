# Replaying the REAL desktop Hunt (2026-10-05)

Source: `Maxchea20/mib-trader-desktop` (read-only; nothing in it was changed). The research port that produced every "Hunt V3 / V4" number in this repo is NOT the desktop engine.

## What the desktop engine really is (from its code)
| Piece | Desktop (`backend/src/brain/*`) | Research port used for V4 |
|---|---|---|
| Thesis / direction | Latest CLOSED 15m BOS/CHoCH from `market_state/builder.py`: swings confirmed by 2 bars each side; a close that CROSSES the active swing high/low fires once. CHoCH = a break against the current structure direction, BOS = with it | Direction = type of the latest tiny pivot (5 or 2 bars). "CHoCH" = the pivot type flipped. Not the same event |
| Invalidation | Frozen parent swing (opposite side); price through it resets the thesis. One ticket per thesis | none |
| Entry paths | SLOT3 (confirmed 15m event -> fire in the NEXT 15m candle), S1 (forming 15m developing BOS/CHoCH in slot 1/2 + a same-direction 5m event -> C), S2 (extension -> pullback of 0.25-0.5 ATR near the origin or S/R -> new 5m event -> C) | one path: a 5m close at least 0.15 ATR beyond the last 15m high/low |
| C (entry timing) | first 1m CLOSE crossing the 5m event's level inside an already-closed 5m window. The FIRE price is therefore a PAST price | n/a |
| Weather | V1b: 4h votes, 1h veto, and a 1.0 ATR retrace off the 4h extreme turns SWING into CHOP | V1, no retrace |
| Live order | MEXC Isolated MARKET order with attached SL/TP at the FRESH ticker price; SL/TP distances (1.5 / 2.5 x 15m ATR) taken from the FIRE | next 1m open after the 5m close |
| Exits | Hard SL, TP, and a lifecycle brain: EXIT on a NEW closed 15m CHoCH against the trade, or when a new 15m closes beyond BOTH the frozen parent and the frozen level. "Trail is OFF" | SL/TP plus "Floors" (a trail the desktop explicitly refuses) |
| Guards | weather block, one position, cooldown 3 x 5m after a HARD_SL | none |
The desktop's own docs say historical replay of this architecture "is still required before treating performance as validated", and its backtest script imports a module (`observation_hunt`) that no longer exists.

## The replay (`scripts/desktop_hunt_replay.py`)
Calls the real `evaluate_hunt`, `classify` (weather), `si_checklist` and `reevaluate` unchanged, with the live data windows (320 closed 15m, 960 5m, 400 1m, 300 4h, 400 1h) and a replay clock (`now_ts`). Phase 1 records every FIRE; phase 2 trades them with the live guards in two models:
PAPER (what the desktop's paper pipe assumes: FIRE price entry, exact SL/TP, no slippage) and REALISTIC (market order after latency at the next 1m open, SL/TP from the live fill price with the FIRE's distances, SL/TP executed on 1m bars by the execution simulator, lifecycle kills as market exits after the closed 5m).
Tests (`tests/test_desktop_replay.py`): windows hold only closed candles; cutting the data never changes earlier FIREs (no future data); realistic fills come after the FIRE; one position at a time; deterministic.
Assumptions that the live logs should settle: latency 1 s, slippage 0.5 bp + 1 tick, whether MEXC's attached TP behaves as a resting limit or a trigger-market order (the simulator treats it as a resting limit with a one-tick trade-through).
Usage: `py scripts\desktop_hunt_replay.py research_binance days=90 desktop=<path>\mib-trader-desktop\backend` (needs numpy; about 0.01 s per 5m close, roughly 20 minutes for 13 months).
