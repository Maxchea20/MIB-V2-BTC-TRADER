# The Hunt V4 story (written 2026-10-05)

## What Hunt is
Desktop Hunt C-FI, ported to the research engine. 4H/1H "weather" says swing up, swing down or chop. On the 15m a fresh BOS/CHoCH gate (cfast, internal, rearm) arms a trade.
The trigger is a 5m candle that closes beyond the prior 15m high/low by at least 0.15 ATR. Stop 1.5 x 15m ATR, target 2.5 x 15m ATR (1.67R), fee 2 bp a side, one position, 15 minute pause after an exit.
The stop is about 0.4% of price, so fees alone cost about 0.1R a trade.

## How it was built up
1. **Hunt (lock 2):** the rule port. Reported +392R / +798R / +211R on the three files.
2. **Hunt V3 (lock 3):** a 1h "failed push" box switch. While the box is on, drop Hunt and trade a chop book instead (reject at a line, stop on a close through the line, target the other line). A look-ahead bug (the box read the 1h bar still forming) was found and fixed.
3. **Floors:** the stop moves to +1R once the best price is 1.75 ATR, to +2.0 ATR at 2.25 ATR. Eye, partials, trails, hour filters, Step 8 and the swing label were tried and dropped.
4. **Hunt V4 = Hunt V3 + Floors** (locked 2026-10-04). Reported +230R / +636R / +203R, worst dips -40R / -19R / -23R. Throttle (half size 10R under the peak) was a later add-on.

## Why the edge looked thin, and the question that broke it
Average per trade was only about 0.1R, and you kept asking why. Then you asked how the entry fills "mid air". The fill_gap_check showed:
- the backtest filled at the broken level, but the signal is only known when the 5m candle CLOSES beyond it, so that price had already gone;
- 11% of entries were not even traded inside the signal candle; the median gap to the first real price was +0.18R, 35% worse than 0.25R;
- with a real fill (next 1m open + slippage) Hunt goes from +0.107R to about -0.12R (research_binance: +211R became -250R to -330R).

## Why filling earlier does not save it
- Split by gap size, the fake-fill R rises with the gap (-0.08 -> +0.41R), because a big gap means the move had already run. The real-fill R is flat at about -0.09R to -0.18R in every bucket.
- A resting stop order at the level on every touch (no waiting for the close): -0.117R. A limit at the level waiting for a retest: -0.144R filled; the missed runners made +0.5R to +0.9R at the fake price and cannot be bought.
- So the signal is selected by the future (the close) and the fill was booked before it. Without that, the gross edge is about zero and costs make it negative.

## What else was fake
- Hunt V4 in the engine with realfill: -0.082R, -105R, dip -117R (research_binance, 1,286 trades).
- The chop book entered at a real price, but booked its stop at the line instead of the 1h close: real stop gives -0.41R, -0.04R, -0.01R on the three files.
- Lock 1 (4h/1h/15m stack) had the same close-then-fill-in-the-past cheat. Random price data showed a profit under the old fill.

## What did work, a little
Only with a swing-size stop (2.0 x 4H ATR, about 2% of price) and a 4R to 5R target: +0.25R to +0.31R pooled over three files (see docs/REAL_FILL_FINDINGS.md). Win rate 20% to 25%, about 40 to 60 trades a year.

## Entry research (this branch)
`scripts/hunt_entry_scan.py` splits real-fill Hunt trades by what is known at the signal and reports two exits. A bucket is only interesting if it beats ALL on every file by more than the cost drag (about 0.1R to 0.15R).
