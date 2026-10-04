# Versions and names

**Latest lock: Hunt V4 (Hunt V3 + Floors), locked 2026-10-04T12:28:04Z** (`config/experiments/lock-4-hunt-v4.md`)

One name for each thing. Numbers are total R / worst drop (dip) in R, for 2019-21, 2022-25, 2025-26. At $50 risk, 1R = $50. Per-year dollars use 2.0, 3.67 and 1.08 years.

## Building blocks
- **Hunt**: the desktop Hunt C-FI entries (weather V1, gates C-fast / internal / rearm). Stop 1.5 ATR, target 2.5 ATR. One position. 15 minute pause after an exit.
- **Floors**: an exit add-on. Once the best price is 1.75 ATR the stop moves up to +1R (1.5 ATR). Once it is 2.25 ATR the stop moves up to +2.0 ATR. Target stays 2.5 ATR.
- **Throttle**: a size rule. Trade at half size while the account is 10R or more below its peak.
- **Box**: the 1h failed-push range detector. Only closed 1h bars count (fixed 2026-10-04; before that it peeked at the forming bar).
- **Chop book**: trades the box lines. Entry on a line reject, stop on a close through the line, target the other line.

## Versions
| Name | What it is | Total R / dip | $ per year at $50 | Status |
|---|---|---|---|---|
| **Hunt** | Hunt entries, stop 1.5 ATR, target 2.5 ATR (lock 2) | +392 / -26.6, +798 / -27.9, +211 / -32.3 | $9,800, $10,900, $9,800 | baseline |
| **Hunt + Floors** | Hunt with Floors | +536 / -28.5, +1156 / -41.4, +325 / -28.9 | $13,400, $15,700, $15,000 | tested in the full engine |
| **Hunt + Floors + Throttle** | Hunt + Floors with Throttle | +474 / -22.2, +1074 / -31.0, +292 / -20.1 | $11,900, $14,700, $13,500 | current leader. Throttle tested on the trade list, not yet in the engine |
| **Hunt V3** | Hunt + box filter (drop Hunt trades while the box is on) + chop book (lock 3) | corrected: +174 / -54.4, +520 / -21.9, +161 / -16.6 | $4,350, $7,100, $7,450 | corrected for the box peek. Old numbers were higher |
| **Hunt V4** = Hunt V3 + Floors | Hunt V3 with Floors, corrected | +230 / -39.9, +636 / -19.1, +203 / -22.7 | $5,750, $8,700, $9,400 | LATEST lock, 2026-10-04T12:28:04Z. Box fixed. Old (peeked) numbers were +263 / +709 / +228 |
| **Chop book** | the chop book alone | +79 / -26.4, +206 / -31.2, +66 / -16.8 | | positive on all files, not affected by the box peek |
| **Swing Hunt + Chop** (test) | Hunt only in swing weather + chop book | +100 / -29.3, +224 / -24.4, +122 / -19.6 | | Hunt side used the peeking box, needs a re-run. Not a lock |

## Ideas tried and dropped
| Idea | Result |
|---|---|
| Step 8 room-to-run veto | worse than baseline on 2022-25 |
| Hunt only at 12-16h UTC, or 08-24h UTC | more profit per trade, less total profit. Not better on every file |
| Breakout trade after a chop stop (3 TP/SL sets) | all lose money (2025-26) |
| Swing label as a filter | unreliable: -0.07R to +0.24R depending on the file |
| Partial sells at 1.0 or 1.4 ATR, smaller targets, trails, give-back | cut the drop, no extra profit. Floors replaced them |
| The eye (closed and forming candle rules) | adds nothing beyond the floors, and lowers profit when added |
| Day cap, pause after losses | day cap mixed, pause did little. Losses do not cluster |
| Box half (half size inside the box) | not tested with the fixed box |

## Not tested
Lock 1 (4h/1h/15m stack), the older S1-S4 and W1 setups, fee and slippage stress, ETH and other coins, and live order handling.
