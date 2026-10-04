> **INVALID (2026-10-04): every Hunt / Hunt V3 / Hunt V4 number in this file used a fake fill.**
> The backtest filled Hunt at the broken 15m level, but the signal is only known when the 5m candle closes beyond it, so that price was no longer available.
> With the real fill (next 1m open after the close, `realfill` flag) Hunt alone is about -0.12R per trade and Hunt V4 on research_binance is -0.082R, -105R, dip -117R.
> Do not trade or build on these results. The chop book already used a real fill (next 1h open); judge it separately (`py scripts\show_chop.py`).

# Lock 4: Hunt V4

**Status: LATEST**
**Locked: 2026-10-04T12:28:04Z**

Hunt V4 is Hunt V3 plus Floors. It replaces Hunt V3 as the baseline. Lock 3 (Hunt V3) stays on record.

## Rule

- Hunt: the desktop Hunt C-FI file, same entries as lock 2 and lock 3. Stop 1.5 ATR, target 2.5 ATR. Fee 2 bp a side. Same-bar stop wins.
- Floors: once the best price is 1.75 ATR in favor, the stop moves up to +1R (1.5 ATR). Once the best price is 2.25 ATR in favor, the stop moves up to +2.0 ATR. A floor takes effect from the next 1m bar. The target stays 2.5 ATR. A trade that never reaches 1.75 ATR keeps the 1.5 ATR stop.
- Box switch, as Hunt V3: the 1-hour failed-push box is on, the Hunt signal is dropped. The box is off, Hunt trades. The box state uses only 1h bars that have closed (fixed 2026-10-04).
- Chop book, as Hunt V3: entry on a line reject or an outer-quarter turn, stop on a close through the entry line, target the other line.
- One position. If either book is in a trade, the other waits. Hunt pauses 15 minutes after an exit.

## Code
- Floors: `src/btc_research/setups/hunt_exits.py`, mode `floors`. Tested against the replay in `tests/test_hunt_exits.py`.
- Hunt with floors: `py scripts\backtest_desktop_cfi.py backend\<file>.db floors`
- Switch and chop on that Hunt file: `py scripts\backtest_hunt_chop.py backend\<file>.db <floors trades.csv>`
- Check against the box peek: `py scripts\run_box_lag_check.py <file> floors`

## Evidence (box fixed)

Hunt floors files: 2019-21 20261004T075627Z, 2022-25 20261004T081919Z, 2025-26 20261004T074410Z. Box check run on 2026-10-04.

| File | Trades | Avg R | Total R | Worst drop | R/dip | $ per year at $50 | Worst drop at $50 |
|---|---|---|---|---|---|---|---|
| 2019-21 | 2027 (Hunt + chop) | +0.114 | +230 | -39.9R | 5.8 | about $5,750 | $1,995 |
| 2022-25 | 3420 | +0.186 | +636 | -19.1R | 33.4 | about $8,700 | $955 |
| 2025-26 | 1229 | +0.165 | +203 | -22.7R | 8.9 | about $9,400 | $1,135 |

Against Hunt V3 with the same fixed box: total R +32%, +22%, +26%. Worst drop better on 2019-21 and 2022-25, worse on 2025-26.

## Known weak points
- The 2019-21 drop is -39.9R, about $2,000 at $50 risk.
- After the box fix, the box filter helps only on 2022-25.
- Hunt + Floors + Throttle (no box, no chop book) earns more on every file: about $11,900, $14,700 and $13,500 a year, worst drops about $1,110, $1,550 and $1,005. It is not part of this lock.
- Tested on three files only. No fee and slippage stress, no paper trading.
- It takes about 2.5 to 3 trades a day.

## Not in this lock
- Throttle (half size while 10R below the equity peak), the eye, partial sells, hour filters, the Step 8 veto, the breakout after a chop stop.
