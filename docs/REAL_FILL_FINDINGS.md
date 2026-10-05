# Real-fill findings (2026-10-04)

Rule for every experiment: the signal is known at a bar close, the fill is the first 1m open after it plus slippage. Never fill at a price from before the signal.
Check any new engine on random-walk data first: it must show about zero (minus costs), not a profit.

## What was wrong
- Hunt, Hunt V3, Hunt V4, floors, throttle: filled at the broken 15m level, before the 5m close that created the signal. All numbers invalid.
- Lock 1 (exp-mtf-4h-1h-15m-v1): same cheat at 15m scale (bar must close beyond the level, fill booked at the level inside that bar). +0.230R, 50% win was fake. On random data it showed a profit.
- Chop book: real entry, but the stop was booked at the line instead of the close of the 1h bar that closed through it. With the real stop: -0.41R, -0.04R, -0.01R (3 files).

## Real-fill results
- Hunt, market order at the next 1m open: about -0.12R to -0.14R per trade. A resting stop on every touch: -0.12R. Limit at the level: -0.14R to -0.15R.
- Hunt V4 in the full engine with realfill: -0.082R, -105R, dip -117R (research_binance).
- S1 pullback (exp-s1-structure-v1): -0.382R, win 38%, dip -150R (research_binance).
- Small stops (about 0.4% of price) lose to fees and the fill gap, whatever the entry.

## The one candidate (not proven, not a lock)
15m close beyond the prior 20-bar high / low, both sides, no 4H or 1H gate (h4_gate=any, h1_gate=any), market order at the next 1m open, stop 2.0 x 4H ATR, target 4R to 5R.
Avg R: research_binance +0.441 (n=38, 4R) / +0.287 (n=33, 5R); 2019-21 +0.166 (94) / +0.344 (73); 2022-25 +0.258 (167) / +0.291 (126). Pooled about +0.25R to +0.31R.
Win rate 20% to 25%. Low frequency (about 40 to 60 trades a year). Pooled about 2 standard errors. Sensitive to small fill changes.
Still to run: `py scripts\mtf_robust.py <db>` on all three files (grid 1.5 to 3.0 ATR, 3R to 6R, cost stress, order 1 to 3 minutes late, win rate and PF in R). Then paper trading before any live money.

## Tools
`scripts/run_mtf_fill_tests.py`, `scripts/mtf_robust.py`, `scripts/forensic_mtf_fill.py`, `scripts/forensic_fill_early.py`, `scripts/fill_gap_check.py`, `scripts/chop_real_stop.py`, `scripts/build_viewer.py` (trade viewer).
Engine flag: `backtest_desktop_cfi.py ... realfill`. MTF options: `fill_mode` (legacy / next_open / touch), `atr_tf`, `h4_gate`, `h1_gate`, `entry_delay_minutes`.

## Engine default (2026-10-05)
`scripts/backtest_desktop_cfi.py` now fills at the next 1m open after the CLOSED 5m signal candle, plus slippage, by default (`_real_entry_after_signal`). The level is only the trigger, never the fill.
The old fill is only available with the `fakefill` flag (to reproduce the invalid numbers; trades are tagged `fill_reference=LEVEL_FAKE`, `fake_fill_removed=False`, results go to a `-fakefill` folder). The `realfill` flag is still accepted and does nothing.
Every trade row now carries `level`, `signal_time`, `signal_price`, `fill_reference`, `fake_fill_removed`, and the engine raises if an entry opens before its signal closed.
`close_time` in this repo is the exclusive end of a bar (= the open of the next 1m candle), so the first executable candle is `open_time >= signal close_time`. A strict `>` would enter one minute late.
Checked on random data: the new default reproduces the old `realfill` trades exactly (2,355 of 2,355), and `fakefill` reproduces the old fake trades exactly (2,380 of 2,380).
