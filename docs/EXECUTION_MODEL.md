# Execution model (2026-10-05)

The strategy decides WHAT to trade. The execution simulator (`src/btc_research/execution/`) decides WHETHER an order could really have been filled and AT WHAT PRICE, from 1m data.
A Hunt FIRE is a signal, not a trade. Lifecycle: SIGNAL (closed candle) -> order submitted at signal_time + latency -> executable? -> FILLED or MISSED_FILL -> protective orders live from fill + latency -> exit.

## Rules
- Structure uses CLOSED candles only. `resample` no longer emits a partial final candle (a test caught that it did).
- **Market entry:** first 1m bar that opens at or after the submit time, at its open, plus slippage against you. Any latency > 0 crosses a minute boundary, so the fill is the next 1m open.
  Optional price protection `max_entry_slippage_bps` (IOC-style): if the price has run further, the order is MISSED_FILL and no trade exists. Default: none (plain market order).
- **Limit order (generic, not used by Hunt V4):** rests from the submit time. A bar that opened before submission can never fill it. Buy fills only when a later bar trades THROUGH the price by `limit_trade_through_ticks`. Untouched = MISSED_FILL.
- **Stop-loss (resting stop-market):** triggers when a 1m bar trades through it. A bar that opens beyond the stop (gap) fills at the OPEN, otherwise at the stop price. Slippage is always added against you. The exit time inside the bar is unknown, so it is booked at the end of that bar.
- **Take-profit (resting limit):** needs a trade-through, fills at its price (a resting order never gets better), no slippage.
- **Protective orders** only exist from fill time + latency, and can only be triggered by later price action. Floors (strategy logic) are unchanged; only the fills are.
- **Stop and target in the same 1m bar:** `intrabar_policy` = `conservative` (stop, the default and the primary result), `optimistic` (target) or `unresolved` (flagged `UNRESOLVED_BOTH_HIT`, excluded from the PnL, counted in the audit).
- **Chop book:** entry is a market order after the reject bar closes. Target = resting limit at the other line (1m trade-through). Stop = a 1h close through the line, known only at that hour's close, so a market exit is submitted then (+ latency).
- R is still net PnL / the planned risk (1.5 ATR for Hunt), so an exit worse than the stop is worse than -1R.

## Assumed values (NOT calibrated to MEXC)
`execution_latency_seconds` 1.0 (guess), `entry_slippage_bps` / `exit_slippage_bps` 0.5 and 1 tick (carried over from every earlier engine), `fee_bps_per_side` 2.0 (taker, as every earlier run), `limit_trade_through_ticks` 1.0 (queue proxy),
`tick_size` 0.1 (Binance default). Leverage, isolated margin and a liquidation check exist as config fields but are off (`None`) until real values are supplied. Funding is not applied.
The real MEXC order/fill logs are not in this repository, so none of these could be calibrated. Replace them from the logs when available.

## How to run
`py scripts\execution_audit.py research_binance` prints OLD vs ENTRY-ONLY vs REALISTIC for Hunt alone and Hunt V4, execution statistics, and what happened to every old trade. It writes `results\execution_audit\<file>\` (report.txt, fires.csv with one row per FIRE, trades_old.csv, trades_realistic.csv).
Options: `latency=0` (best case on 1m data), `latency=1`, `entry-slip=`, `exit-slip=`, `intrabar=conservative|optimistic|unresolved`.
Engine: `py scripts\backtest_desktop_cfi.py backend\research_binance.db floors` is now the realistic model; `fakefill` reproduces the old invalid numbers, `ideal-exits` keeps real entries with the old exits.
Tests: `python -m unittest discover tests` (45 tests).

## Trend-gate experiment (2026-10-05, pre-declared)
`py scripts\trend_gate_experiment.py <file>` runs Hunt with floors under the realistic model four ways: ungated / gated by the 1H trend (last closed 1H close vs the close 20 hours earlier), each with the 15m ATR unit (Hunt as designed) and the 1H ATR unit (stop about 1% of price).
Engine switches (default off): `trend-gate=1h|4h`, `atr-unit=1h`. A FIRE against the trend is recorded as `FILTERED_TREND_GATE`. Tests: `tests/test_execution_engine.py::TrendGate`.

## Swing-only experiment (2026-10-05, pre-declared)
`py scripts\swing_only_experiment.py <file>`: Hunt only while the weather says SWING_UP / SWING_DOWN (chop-weather FIREs are recorded as `FILTERED_CHOP_WEATHER`), no box, no chop book, realistic execution, floors on, with the 15m and the 1H ATR unit. CHoCH/BOS, side and gate splits are numbers only, nothing is tuned.
Engine switch (default off): `swing-only`. Test: `tests/test_execution_engine.py::SwingOnly`.

## Breakout-then-retest entry screen (2026-10-05, pre-declared, information test only)
`py scripts\retest_entry_screen.py <file>`: a Hunt FIRE is the breakout; the entry is a market order after a closed 5m candle retests the level (low within 0.10 ATR of it, closes beyond it). Cancelled if a 5m candle closes 0.25 ATR back through the level (failed breakout), price runs 2 ATR beyond it without a retest (ran away), or 24 5m candles pass (expired). One watch at a time.
Output: excess move after the fill (bp, over market drift) for IMMEDIATE breakout entry, RETEST entry, the same signals entered immediately, and the breakouts that never retested, at 15m/1h/4h/12h, for all weather and swing weather. No stops, targets or exits. Tests: `RetestWatch`.
